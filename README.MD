# sync-codex-history

A Codex skill for keeping local Codex history visible after switching between
account login and API-key login on the same machine.

This project does not sync history between computers. Each computer keeps and
repairs visibility for its own local Codex home, such as `%USERPROFILE%\.codex`
on Windows or `~/.codex` on macOS.

## What It Solves

When Codex is used on one personal computer with different login modes, local
threads may still exist on disk but disappear from the current sidebar/search
view. This skill helps Codex inspect the local state, create a backup, identify
hidden local user threads, and restore visibility by forking readable old
threads into the current account context.

## What It Does

- Detects the local Codex home from `CODEX_HOME` or `~/.codex`.
- Backs up local history and state before repair work.
- Inspects `state_5.sqlite`, `sessions`, `archived_sessions`, and
  `session_index.jsonl`.
- Reports local user threads that may be hidden or missing from the current
  index.
- Guides Codex to use App thread tools such as `list_threads`, `read_thread`,
  `fork_thread`, and `set_thread_title` when available.
- Skips internal approval-review, subagent, and non-user threads.

## What It Does Not Do

- It does not copy history between Windows and macOS.
- It does not commit or upload your Codex history.
- It does not modify or copy `auth.json`, API keys, tokens, or credentials.
- It does not sync cloud entitlements, billing, connector authorization, or
  model access.
- It does not directly merge account-side data on OpenAI servers.

## Install

Clone this repository into your Codex skills directory.

### Windows

```powershell
git clone git@github.com:guyueKing/sync-codex-history.git "$env:USERPROFILE\.codex\skills\sync-codex-history"
```

### macOS / Linux

```bash
git clone git@github.com:guyueKing/sync-codex-history.git ~/.codex/skills/sync-codex-history
```

Restart Codex or start a new Codex thread if the skill is not discovered
immediately.

## Usage

Ask Codex:

```text
Use sync-codex-history to sync this machine's Codex history.
```

Or:

```text
Use $sync-codex-history after I switched accounts and my history disappeared.
```

Codex should first inspect and back up local state, then fork only safe user
threads that are readable but not visible in the current account context.

## Manual Inspection

You can run the inspection script directly. It only reports local state when
`--no-backup` is provided.

```bash
python scripts/inspect_codex_history.py --no-backup
```

To create a backup during inspection:

```bash
python scripts/inspect_codex_history.py
```

Backups are written under:

```text
<codex-home>/backups/sync-codex-history-YYYYMMDD-HHMMSS
```

## Safety

This repository contains only the skill instructions and inspection script.
The `.gitignore` prevents accidental commits of live Codex state such as
sessions, backups, SQLite databases, `auth.json`, and local global-state files.

For actual repair work, prefer Codex App thread operations over direct SQLite
edits while Codex is running.
