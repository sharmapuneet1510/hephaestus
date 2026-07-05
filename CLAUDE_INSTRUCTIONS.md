# Claude Code Instructions for Hephaestus

You are implementing Hephaestus, an internal AI coding assistant. Follow these instructions strictly.

## 1. Operating Mode
Always work plan-first.

Before editing code, provide:
1. Goal
2. Files to inspect
3. Files likely to change
4. Step-by-step implementation plan
5. Tests to run
6. Risks or assumptions
7. Expected output

Do not modify files until the plan is clear.

## 2. Task Execution Rule
Use tasklist.txt as the execution source.

For every task/subtask:
- Implement only the current subtask scope.
- Produce a concrete output.
- Run or add tests at the same time.
- Do not mark anything complete unless the output exists and the test passes.
- Update progress only after validation.

Every subtask must result in one of these:
- Working UI section
- Working backend service
- Working API integration
- Working config/schema
- Working test
- Updated project knowledge
- Generated final documentation

## 3. Testing Rule
Code and test together.

For each implementation:
- Add unit tests where practical.
- Add integration tests for service boundaries.
- Run targeted tests first.
- Run broader tests before marking a major task complete.
- If tests fail, stop and create a fix plan.
- Do not hide failed tests.

## 4. CLAUDE.md Knowledge Rule
Maintain CLAUDE.md at repository root.

Create it if missing.
Update it after meaningful completed work with concise notes only.

CLAUDE.md should include:
- Project overview
- Architecture decisions
- Important commands
- Test commands
- Coding conventions
- Config conventions
- Current constraints
- Completed task notes
- Known issues

Do not spam CLAUDE.md with long logs.
Keep it useful for future AI sessions.

## 5. Documentation Rule
Do not waste tokens creating markdown documentation for every task.

During implementation, update only:
- task status if task tracking exists
- CLAUDE.md for durable knowledge
- code comments only where needed

Generate full documentation only at the end or when explicitly requested.

Final documentation should include:
- Setup guide
- Usage guide
- Architecture summary
- Configuration reference
- Agent workflow guide

## 6. Model Selection Rule
Use the correct model for the task.

Recommended routing:
- Simple model: formatting, small explanations, simple UI changes
- Medium model: single feature implementation, bug fixes, unit tests
- Strong model: architecture decisions, multi-file refactors, context engine, repository graph, safety model

Prefer stronger reasoning for:
- Context engine
- Agent execution
- File editing safety
- Model routing
- Large codebase chunking
- Test runner design

## 7. Context Rule
Do not load the entire repository blindly.

When working:
- Inspect relevant files first.
- Use focused context.
- Summarize large files.
- Chunk large files.
- Prefer module-level understanding before repo-level changes.

When user says focus on a module:
- Prioritize that module.
- Include adjacent dependencies only when needed.
- Keep focus visible in implementation notes.

## 8. Safety Rule
Protect the user's workspace.

Never:
- Delete files without explicit approval.
- Run destructive commands without confirmation.
- Modify files outside the repository.
- Expose secrets in logs or prompts.
- Rewrite large sections unnecessarily.

Always:
- Show diffs for file changes.
- Keep patches minimal.
- Preserve existing style.
- Provide revert strategy for risky edits.

## 9. Code Quality Rule
Follow existing project conventions first.

If no convention exists:
- Use clear structure.
- Keep functions small.
- Separate UI, service, config, and execution logic.
- Add validation around file system and shell operations.
- Use typed contracts where possible.
- Prefer readable code over clever code.

## 10. Hephaestus Product Rules
The product must support:
- Chat UI similar to VS Code chat
- Repository loading
- File tree
- Internal AI API integration
- Context generation in markdown, JSON, TOON, and graph formats
- Module focus mode
- Plan-first execution
- Agent task execution from JSON/YAML
- Safe file editing with diff and revert
- Test execution and result capture
- CLAUDE.md updates
- Configurable model routing
- Final documentation generation

## 11. Response Format During Work
For each subtask, respond with:

Current subtask:
Plan:
Changed files:
Tests run:
Result:
CLAUDE.md update:
Next recommended subtask:

Keep responses concise but complete.

## 12. Definition of Done
A subtask is done only when:
- The requested output exists.
- Tests are added or relevant existing tests are run.
- Test result is reported.
- CLAUDE.md is updated if durable knowledge changed.
- No unnecessary documentation files were created.

A major task is done only when all subtasks under it meet the definition of done.

The MVP is done only when the end-to-end journey works:
Load repo -> ask question -> set focus -> create plan -> apply code change -> show diff -> run test -> update CLAUDE.md -> update task status -> generate final docs.
