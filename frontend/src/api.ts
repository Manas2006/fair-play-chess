import type { ReviewCase, ReviewDecision, Summary } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  summary: () => request<Summary>("/api/v1/summary"),
  cases: () => request<ReviewCase[]>("/api/v1/cases?limit=100"),
  decide: (accountId: string, decision: ReviewDecision, reason: string) =>
    request(`/api/v1/cases/${accountId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, reason, reviewer: "portfolio-reviewer" })
    })
};
