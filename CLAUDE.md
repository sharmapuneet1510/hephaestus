# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project State

Early, spec-driven development. **TASK 1–7 are complete**: config/env/health, a three-panel "Forge"
chat UI, SSE streaming chat that calls the internal AI API when configured (else a mock), model
routing, a repository loader, a context engine (chunking + markdown/JSON/TOON/graph + refresh), module
focus, and the plan-first workflow (structured plan endpoint, plan-approval state, Apply-disabled-
until-plan, and an edit guard). TASK 8 (File Editing and Diff Review) onward is not yet built.
Backend stack is **Python/FastAPI** (matches the existing `.claude/` Python hooks); frontend is
React + TypeScript + Vite + Monaco.

Plan-first is enforced end to end: `app/plan.py` builds a structured `Plan`, holds it in `PlanState`
(pending → approved), and `POST /api/edit` returns 400 unless a plan is approved — actual file
editing (applying edits, diffs, revert) arrives in TASK 8.

**AI client:** built on the official **`anthropic` SDK** (`AsyncAnthropic`) pointed at the internal
endpoint via `base_url`. Assumption: the internal AI API speaks the **Anthropic Messages API** shape
(common for internal gateways). If it's OpenAI-shaped instead, only `app/ai_client.py` changes. Model
IDs in `config/default.yaml` (`claude-haiku-4-5` / `claude-sonnet-5` / `claude-opus-4-8`) are current;
when touching AI code, load the `claude-api` skill for authoritative SDK/model details.

## Layout

- `backend/` — FastAPI app. `app/config.py` loads `config/default.yaml`; `app/main.py` is the app
  factory (`/api/health` + serves the built SPA when `frontend/dist` exists); `app/chat.py` is the
  SSE chat endpoint (`POST /api/chat`, `data: {"delta":…}` … `[DONE]`) that streams real AI when
  configured, else a mock; `app/ai_client.py` wraps the Anthropic SDK (`AIClient`, `AIError`);
  `app/routing.py` classifies a request to a model tier; `app/repo.py` loads a local repo
  (`POST /api/repo/load`, `GET /api/repo`) — scan + ignore rules + project-type + `SessionStore`
  persistence to `.hephaestus/session.json`; `app/context.py` is the context engine
  (`POST /api/context/build`, formats `markdown|json|toon|graph`) — chunking, regex symbol/import
  extraction, and a hash-cached `ContextEngine` for refresh. Tests in `backend/tests/`.
- `frontend/` — Vite React app. `src/App.tsx` orchestrates health + chat state; `src/api.ts` has
  `fetchHealth` and `streamChat` (parses SSE via a `fetch` ReadableStream). Components in
  `src/components/`; design system in `src/theme.css` (the "Forge" palette) + `src/app.css`.
  Dev server proxies `/api` → backend (`vite.config.ts`, `loadEnv`-based).
- `config/default.yaml` — single source of non-UI behavior (AI endpoint, model routing, context
  limits, ignore paths, test commands, safety rules). `${ENV_VAR}` placeholders resolve from the
  environment; the AI API key is read by the env-var name in `ai.api_key_env`, never stored in YAML.

## Design language ("The Forge")

The UI commits to a warm industrial-forge identity: heated-iron graphite surfaces, molten-ember
accents (`--ember`, `--ember-hot`, `--ember-core`), verdigris (`--patina`) for success. Fonts are
self-hosted via `@fontsource`: Bricolage Grotesque (display), IBM Plex Sans (body), IBM Plex Mono
(code/labels). Keep new UI consistent with the tokens in `src/theme.css` rather than introducing new
colors/fonts.

## Commands

Backend (from `backend/`, using `uv`):

```bash
uv venv --python 3.11 .venv                 # first-time setup
uv pip install -e ".[dev]" --python .venv   # install deps
.venv/bin/python -m pytest                  # run tests
.venv/bin/python -m pytest --cov=app        # tests + coverage
.venv/bin/python -m pytest tests/test_config.py::test_require_ai_raises_clear_error_when_unset  # single test
.venv/bin/python -m uvicorn app.main:app --reload   # run dev server (:8000)
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev         # Vite dev server (:5173), proxies /api -> backend
npm run test        # Vitest (component tests)
npm run typecheck   # tsc --noEmit
npm run build       # tsc -b && vite build  (emits frontend/dist/)
```

Notes:
- The backend boots and serves `/api/health` **without** a real AI key; health reports
  `ai_configured: false`. AI env vars are only required when an actual AI call is made
  (`AppConfig.require_ai`). `/api/chat` is currently a deterministic **mock** (TASK 3 wires real AI).
- **Single-origin mode (most reliable locally):** run `npm run build`, then start the backend — it
  serves the SPA at `/` with the API same-origin, so no dev proxy is involved. Open the backend URL
  directly (e.g. `http://127.0.0.1:8000`).
- The Vite dev proxy target comes from `VITE_BACKEND_URL` (shell or `frontend/.env.local`). Note: in
  some sandboxed shells Vite caches its bundled config across restarts, so proxy-target changes may
  not take effect until caches clear — prefer single-origin mode when scripting verification.
- Port `8000` may be occupied by another local service; override with `--port <N>`.
- Vite binds `localhost` (IPv6) by default — use `curl http://localhost:5173` (not `127.0.0.1`) or
  pass `--host 127.0.0.1` when scripting checks.
- Set `HEPHAESTUS_STREAM_DELAY_S=0` to disable the chat streaming delay (used in tests).

## Git / Commit Rules

- Commits are authored by the repository owner's user account (`git config user.name` /
  `user.email`) — **not** Claude.
- **Do not add a `Co-Authored-By` trailer** (no Claude co-author / co-owner) or any AI attribution
  to commit messages or PR bodies. Keep messages plain and descriptive.

## What Hephaestus Is

Hephaestus is an internal AI coding assistant (inspired by GitHub Copilot / VS Code chat / agentic
coding workflows). A developer loads a repository, chats with an assistant, focuses on a module,
gets a **plan before any code change**, applies edits with visible diffs, runs tests, and maintains
project knowledge in a `CLAUDE.md` at the target repo's root.

Note: this app *generates and maintains* a `CLAUDE.md` inside repositories it operates on. That is a
product feature — distinct from this file, which governs how to build Hephaestus itself.

## Source-of-Truth Documents

Read these before starting work; they drive everything:

- **`requirement.txt`** — full product spec. Section 6 lists the 14 core feature areas and their
  acceptance criteria. This is the definition of "what."
- **`tasklist.txt`** — the execution plan: 15 TASKS broken into SUBTASKS, each with an OUTPUT and a
  TEST. This is the definition of "in what order." Work is tracked against these.
- **`CLAUDE_INSTRUCTIONS.md`** — the operating rules for implementers (plan-first, test-together,
  safety, model routing, response format). Treat these as binding process rules for this repo.

## Non-Negotiable Working Rules

These come from `CLAUDE_INSTRUCTIONS.md` and `requirement.txt` §5 and are the reason this project
exists — follow them when implementing Hephaestus's own code:

- **Plan-first.** Before editing code, state: goal, files to inspect, files likely to change,
  step-by-step plan, tests to run, risks/assumptions, expected output. Do not edit until the plan
  is clear.
- **One subtask at a time.** Implement only the current subtask's scope (from `tasklist.txt`).
- **Code and test together.** Add unit tests where practical, integration tests at service
  boundaries. A subtask is *not done* until its OUTPUT exists **and** its TEST passes. Never hide a
  failing test — stop and create a fix plan.
- **Maintain knowledge, not noise.** Update `CLAUDE.md` (and task status) after meaningful work with
  concise, deduplicated notes. Do **not** generate per-task markdown files; produce full docs only
  at the end or on explicit request (TASK 14).
- **Safety.** Workspace-only file access; show diffs for every change; keep patches minimal; block
  destructive commands by default; redact secrets from prompts/logs; preserve existing code style.
- **Model routing.** Use lighter models for simple work, stronger reasoning for the context engine,
  agent execution, file-editing safety, model routing, large-codebase chunking, and the test runner.

Per-subtask response format (from `CLAUDE_INSTRUCTIONS.md` §11): Current subtask / Plan / Changed
files / Tests run / Result / CLAUDE.md update / Next recommended subtask.

## Intended Architecture (per requirement.txt §7)

Not yet built — this is the target the tasklist builds toward:

- **Frontend:** React + TypeScript + Vite, Monaco Editor. Three-panel layout: repository tree · chat
  area · task/status panel. Streaming responses (WebSocket/SSE).
- **Backend:** Node/TypeScript or Python/FastAPI. Services for filesystem workspace access and
  controlled shell execution; streaming to the UI.
- **Storage:** local JSON/SQLite for sessions, tasks, summaries, config.
- **AI integration:** internal office AI API behind a reusable client abstraction, with
  config-driven model routing (simple / medium / strong tiers).

Keep UI, service, config, and execution logic separated (CLAUDE_INSTRUCTIONS.md §9). Most non-UI
behavior must be config-driven via YAML/JSON (endpoint, model routing, ignore paths, test commands,
safety rules, task-file location) — see requirement.txt §6.10.

Core subsystems to be built (requirement.txt §6): Chat UI, Repository Loader (respects `.gitignore`,
excludes `node_modules`/`target`/`build`/`dist`/`.git`), Context Engine (markdown / JSON / TOON /
graph formats, chunking, summaries), Module Focus Mode, Plan-First Workflow, File Editing + Diff,
Test Runner, Agent Task Execution, CLAUDE.md maintenance, Safety/Permissions, Model Routing,
Large-Codebase support (chunking + retrieval + token budget), Final Documentation Generator.

## The `.claude/` Toolkit

This repo ships a custom Claude Code toolkit — reuse it rather than reinventing:

- **`.claude/agents/`** — role agents (architect, business_analyst, implementer, quality,
  orchestrator), their `functions/` (build, test, review, design, security, docker, iac, …), and
  `modules/`. `agents/instructions/master_instruction_set.md` holds universal coding-agent rules.
- **`.claude/skills/`** — reusable capability guides (Java/Spring/Lombok, Python, React, database/
  MSSQL, Apache Camel/Pulsar, OpenTelemetry, logging, error handling, code review, OOP, testing, …).
- **`.claude/hooks/`** — currently **sample/template** hooks, not wired via a `settings.json`. They
  assume a Python `tools/` layout: `code-format-check.sh` (black + isort), `test-runner-pre-commit.py`
  (`pytest tools/ --cov=tools`), `promptshield-check.sh` (blocks dangerous prompt patterns). If you
  adopt them, add a `.claude/settings.json` and confirm the paths match the actual layout chosen.

<!-- Build/test commands are documented under "## Commands" near the top of this file. -->
