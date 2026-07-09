# 🔨 Hephaestus

> **Forge better software with agentic code intelligence.**

Hephaestus is an internal, AI-powered coding assistant inspired by GitHub Copilot, VS Code chat,
and agentic coding workflows. It connects to an internal AI API and gives developers a chat-based
interface that can understand large codebases, focus on a selected module, **plan changes before
executing them**, edit files safely with visible diffs, run tests, and maintain durable project
knowledge in a `CLAUDE.md`.

## ✨ Core Capabilities

- **Chat UI** — VS Code–style conversation with streaming responses, code rendering, and file chips.
- **Repository Loading** — scan a local repo's file tree, respecting `.gitignore` and ignore rules.
- **Context Engine** — generate AI-friendly context in Markdown, JSON, TOON, and dependency-graph
  formats, with chunking and summaries for large files.
- **Module Focus Mode** — tell the assistant to *focus on a module* and prioritize it in context.
- **Plan-First Execution** — every code change begins with a reviewable plan (goal, files, steps,
  risks, tests, expected output).
- **Safe File Editing** — apply patches with diffs and revert, restricted to the workspace.
- **Test Runner** — detect and run test commands, capture results, feed failures back into fixes.
- **Agent Task Execution** — run tasks/subtasks defined in JSON/YAML, tracking progress.
- **Model Routing** — route requests to the right model tier by task complexity.
- **Knowledge Maintenance** — keep a concise `CLAUDE.md` in the target repo up to date.

## 🚀 Run the Web App

Hephaestus is a local app: a **Python/FastAPI backend** reads the repo and talks to the AI, and a
**React SPA** is the UI. The most reliable way to run it locally is **single-origin mode** — build
the frontend once, then let the backend serve it so the UI and `/api` share one origin (no dev proxy).

**Prerequisites:** Python 3.11+, Node 20+, and [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Build the frontend (emits frontend/dist/)
cd frontend
npm install
npm run build

# 2. Set up and start the backend (from the repo root)
cd ../backend
uv venv --python 3.11 .venv
uv pip install -e ".[dev]" --python .venv
.venv/bin/python run_server.py        # serves UI + API on http://127.0.0.1:8899
```

Open **http://127.0.0.1:8899**, then **paste a local repository path** into the Repository panel to
load a codebase and start chatting. (A browser can't hand a real filesystem path to the backend, so
the web app takes a pasted path; the [desktop app](DESKTOP.md) adds a native "Open Folder" picker.)

**AI keys are optional.** Without them the app runs on a deterministic **mock** so you can explore the
full flow. To connect the real internal AI, set the endpoint and key before starting the backend:

```bash
export HEPHAESTUS_AI_ENDPOINT="https://your-internal-ai-gateway"
export HEPHAESTUS_AI_API_KEY="…"      # read via the env-var name in config/default.yaml
```

**Live-reload development** (two terminals, Vite proxies `/api` → backend):

```bash
cd backend  && .venv/bin/python -m uvicorn app.main:app --reload --port 8899   # terminal 1
cd frontend && npm run dev                                                     # terminal 2 → http://localhost:5173
```

> Want to see the UI without running anything? There's an
> [interactive demo of the Forge interface](https://claude.ai/code/artifact/0de2f120-83eb-4147-b9bc-23e24c973eab)
> (mock-backed — load the sample repo, plan a change, apply, run tests).

## 📐 Intended Tech Stack

- **Frontend:** React + TypeScript + Vite, Monaco Editor (three-panel layout: repo tree · chat ·
  task/status).
- **Backend:** Node/TypeScript or Python/FastAPI with WebSocket/SSE streaming, filesystem workspace
  service, and a controlled shell-execution service.
- **Storage:** local JSON/SQLite for sessions, tasks, summaries, and config.
- **AI:** internal AI API behind a reusable client with config-driven model routing.

## 🗺️ Project Status

**MVP complete** — all 15 tasks in `tasklist.txt` are done (backend 123 tests / 93% coverage,
frontend tests + typecheck + build clean; end-to-end journey validated). The product spec, execution
plan, and implementer rules live in:

- [`requirement.txt`](requirement.txt) — full product specification and acceptance criteria.
- [`tasklist.txt`](tasklist.txt) — the 15-task execution plan toward the MVP.
- [`CLAUDE_INSTRUCTIONS.md`](CLAUDE_INSTRUCTIONS.md) — plan-first / test-together operating rules.
- [`CLAUDE.md`](CLAUDE.md) — guidance for AI coding agents working in this repo.

## 🤖 Built With Awesome Prompts

This project's AI agent scaffolding — the role-based agents, reusable skills, and hooks under
[`.claude/`](.claude/) — was created with the help of
**[Awesome Prompts](https://github.com/sharmapuneet1510/awesome-prompts)**, an enterprise-grade
system of role-based AI agents and reusable skills for autonomous code generation. Hephaestus uses
that toolkit's agents (architect, business analyst, implementer, quality, orchestrator) and skills
to drive its own plan-first, test-together development workflow.
