# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project State

This is a **greenfield, spec-driven project**. No application code exists yet — only planning
documents and a `.claude/` toolkit. The first real work is bootstrapping the project skeleton
(tasklist.txt TASK 1). Do not assume build/test tooling exists; establish it as tasks require it.

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

## Commands

No build/lint/test commands are established yet — the project skeleton does not exist. Define them as
part of TASK 1 (Project Bootstrap) and record the real commands here once they work. The sample hooks
above imply an intended Python path (`black`, `isort`, `pytest --cov`), but the tech stack is not yet
committed; do not treat those as authoritative until code exists.
