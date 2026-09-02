SHELL := /bin/bash

.PHONY: install demo real api ui test build load-test

install:
	python3 -m venv .venv
	.venv/bin/pip install -e 'backend[dev]'
	cd frontend && npm install

demo:
	.venv/bin/fairplay demo

real:
	STOCKFISH_PATH=$${STOCKFISH_PATH:-$$(command -v stockfish)} .venv/bin/fairplay real

api:
	.venv/bin/uvicorn fairplay.api:app --app-dir backend --reload --host 127.0.0.1 --port 8000

ui:
	cd frontend && npm run dev

test:
	.venv/bin/pytest backend/tests
	cd frontend && npm run lint

build:
	cd frontend && npm run build

load-test:
	.venv/bin/python scripts/load_test.py
