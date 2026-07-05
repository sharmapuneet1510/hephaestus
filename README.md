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

## 📐 Intended Tech Stack

- **Frontend:** React + TypeScript + Vite, Monaco Editor (three-panel layout: repo tree · chat ·
  task/status).
- **Backend:** Node/TypeScript or Python/FastAPI with WebSocket/SSE streaming, filesystem workspace
  service, and a controlled shell-execution service.
- **Storage:** local JSON/SQLite for sessions, tasks, summaries, and config.
- **AI:** internal AI API behind a reusable client with config-driven model routing.

## 🗺️ Project Status

Early, spec-driven development. The product spec, execution plan, and implementer rules live in:

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
