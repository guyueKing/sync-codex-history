# sync-codex-history

A Codex skill for keeping local Codex history visible after switching between
account login and API-key login on the same machine.

This project does not sync history between computers. Each computer keeps and
repairs visibility for its own local Codex home, such as `%USERPROFILE%\.codex`
on Windows or `~/.codex` on macOS.

## What It Solves

When Codex is used on one personal computer with different login modes, local
threads may still exist on disk but disappear from the current sidebar/search
view. Local settings, installed skills, plugin-provided skills, and pet/avatar
state may also still exist on disk but not be loaded by the newly active account
or thread. This skill helps Codex inspect the local state, create a backup,
identify hidden local user threads, restore thread visibility by forking
readable old threads, and optionally restore local continuity state from a
trusted backup.

## What It Does

- Detects the local Codex home from `CODEX_HOME` or `~/.codex`.
- Backs up local history, settings, skills, plugins, and pet state before repair
  work.
- Inspects `state_5.sqlite`, `sessions`, `archived_sessions`, and
  `session_index.jsonl`.
- Reports local user threads that may be hidden or missing from the current
  index.
- Reports a safe local-state manifest for settings files, `skills`, `plugins`,
  and `pets` without printing file contents.
- Guides Codex to use App thread tools such as `list_threads`, `read_thread`,
  `fork_thread`, and `set_thread_title` when available.
- Skips internal approval-review, subagent, and non-user threads.
- Can restore local settings, skills, plugins, and pets from a previous backup
  while leaving credentials untouched.

## What It Does Not Do

- It does not copy history between Windows and macOS.
- It does not commit or upload your Codex history.
- It does not modify or copy `auth.json`, API keys, tokens, or credentials.
- It does not sync cloud entitlements, billing, connector authorization, or
  model access.
- It does not directly merge account-side data on OpenAI servers.
- It does not make a running Codex thread reload skills immediately; restart
  Codex or open a new thread after restoring local state.

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

## Restore Local Settings, Skills, Plugins, And Pets

Use this only with a backup you trust. The restore command first creates a new
rollback backup of the current state, then replaces only local continuity state:

- `.codex-global-state.json`
- `.codex-global-state.json.bak`
- `config.toml`
- `AGENTS.md`
- `.personality_migration`
- `chrome-native-hosts-v2.json`
- `pets/`
- `skills/`
- `plugins/`

It does not restore `auth.json`, `cap_sid`, API keys, tokens, or account
credentials.

```bash
python scripts/inspect_codex_history.py \
  --codex-home ~/.codex \
  --restore-local-state-from ~/.codex/backups/sync-codex-history-YYYYMMDD-HHMMSS
```

On Windows:

```powershell
python scripts\inspect_codex_history.py `
  --codex-home "$env:USERPROFILE\.codex" `
  --restore-local-state-from "$env:USERPROFILE\.codex\backups\sync-codex-history-YYYYMMDD-HHMMSS"
```

After restoring, restart Codex or start a new thread so settings, skills,
plugin-provided skills, and pet state are loaded again.

## Safety

This repository contains only the skill instructions and inspection script.
The `.gitignore` prevents accidental commits of live Codex state such as
sessions, backups, SQLite databases, `auth.json`, local settings, skills,
plugins, pets, and local global-state files.

For actual repair work, prefer Codex App thread operations over direct SQLite
edits while Codex is running.
