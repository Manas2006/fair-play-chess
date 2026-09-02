from __future__ import annotations

import argparse
import asyncio
from statistics import mean
from time import perf_counter

import httpx


async def hit(client: httpx.AsyncClient, url: str) -> float:
    started = perf_counter()
    response = await client.get(url)
    response.raise_for_status()
    return (perf_counter() - started) * 1000


async def run(base_url: str, requests: int, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=10) as client:
        async def limited() -> float:
            async with semaphore:
                return await hit(client, f"{base_url}/api/v1/cases?limit=50")
        latencies = await asyncio.gather(*(limited() for _ in range(requests)))
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print({"requests": requests, "concurrency": concurrency, "mean_ms": round(mean(latencies), 2), "p95_ms": round(p95, 2)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=25)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.requests, args.concurrency))
