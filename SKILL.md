---
name: sync-codex-history
description: Keep a local Codex installation's history, settings context, and account/API-login continuity visible after switching Codex accounts or API authentication on the same machine. Use when the user says Codex history disappeared, account switching changed the sidebar, API login hides previous chats, local settings/skills/pet state seem missing, or asks to sync/restore Codex history on the current computer.
---

# Sync Codex History

Use this skill to preserve a single-person local Codex environment across account/API login switches on the current computer.

## Local Scope

- Codex home is usually `%USERPROFILE%\.codex` on Windows or `~/.codex` on macOS/Linux unless `CODEX_HOME` is set.
- Local history lives mainly in `sessions\`, `archived_sessions\`, `state_5.sqlite`, and `session_index.jsonl`.
- Local UI/personality/pet settings live mainly in `.codex-global-state.json` and `pets\`.
- Local skills and plugins usually live in `skills\` and `plugins\`.
- Local model/provider and agent defaults may live in `config.toml` and `AGENTS.md`.
- Do not print secrets, prompt history, server credentials, API keys, tokens, or full rollout content.

## Workflow

1. Run `scripts/inspect_codex_history.py --codex-home <path>` to create a safe report and backup.
2. Read the report summary from stdout. It lists candidate user threads that exist locally but may not be visible in the current account/API sidebar. It also includes a safe `local_state` manifest for settings files, `skills`, `plugins`, and `pets` without printing their contents.
3. Prefer Codex App tools for history synchronization:
   - Use `codex_app.list_threads` to see what the current login can see.
   - Use `codex_app.read_thread` by thread id to verify hidden local threads are readable.
   - Use `codex_app.fork_thread` with `{"environment":{"type":"same-directory"}}` to copy hidden user threads into the current visible account context.
   - Use `codex_app.set_thread_title` on the new forked thread ids to keep titles clean.
4. Do not fork internal/subagent/approval-review threads. Skip threads whose `thread_source` is not `user`, whose `source` JSON mentions `subagent`, or whose title begins with approval-review transcript text.
5. If settings, skills, plugins, or pet state are missing after an account switch, restore local continuity state only from a trusted backup:
   - Run `scripts/inspect_codex_history.py --codex-home <path> --restore-local-state-from <backup-dir>`.
   - This creates a fresh rollback backup before replacing settings files, `skills\`, `plugins\`, and `pets\`.
   - It does not restore `auth.json`, `cap_sid`, API keys, tokens, or credentials.
6. Verify with `codex_app.list_threads` and targeted searches that the new forked threads are visible.
7. Tell the user the backup directory, rollback directory if local state was restored, new visible thread titles/ids, and that Codex must be restarted or a new thread opened for restored skills/plugins/pet state to load.

## Safety Rules

- Always back up before editing or forking many threads.
- Prefer forking old visible/readable threads over direct SQLite updates while Codex is running.
- Do not copy `auth.json` between accounts or modify credentials.
- Do not restore local state from an untrusted backup directory.
- Do not claim restored skills are loaded into the current running thread. Restart Codex or open a new thread after restoring local state.
- Do not synchronize cloud entitlements, connector authorizations, billing, model access, or workspace policy; those are account-side capabilities.
- If the user only asks whether settings are shared, answer from local file layout and do not run synchronization.

## Useful Trigger Phrase

The user can say: `Use sync-codex-history to sync this PC's Codex history`.
