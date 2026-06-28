#!/usr/bin/env python3
"""Inspect local Codex history safely and create a rollback backup.

This script intentionally does not modify Codex state. Use Codex App thread
tools to fork readable hidden user threads into the current account context.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any


THREAD_ID_RE = re.compile(r"019[0-9a-f-]{32,}")

SQLITE_BACKUP_FILES = ("state_5.sqlite", "goals_1.sqlite", "memories_1.sqlite", "logs_2.sqlite")
HISTORY_BACKUP_FILES = ("session_index.jsonl",)
HISTORY_BACKUP_DIRS = ("sessions", "archived_sessions")
LOCAL_STATE_FILES = (
    ".codex-global-state.json",
    ".codex-global-state.json.bak",
    "config.toml",
    "AGENTS.md",
    ".personality_migration",
    "chrome-native-hosts-v2.json",
)
LOCAL_STATE_DIRS = ("pets", "skills", "plugins")
CREDENTIAL_FILES_EXCLUDED = ("auth.json", "cap_sid")


def default_codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codex"


def sqlite_backup(src: Path, dst: Path) -> None:
    src_con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst_con = sqlite3.connect(dst)
    try:
        src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_summary(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "bytes": stat.st_size,
        "modified_at": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "sha256": file_sha256(path),
    }


def directory_summary(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_dir():
        return {"exists": False}

    file_count = 0
    total_bytes = 0
    for child in path.rglob("*"):
        if child.is_file():
            file_count += 1
            try:
                total_bytes += child.stat().st_size
            except OSError:
                pass

    child_names = sorted(child.name for child in path.iterdir())
    stat = path.stat()
    return {
        "exists": True,
        "direct_child_names": child_names[:200],
        "direct_child_names_truncated": len(child_names) > 200,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "modified_at": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def local_state_manifest(base: Path) -> dict[str, Any]:
    return {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "base": str(base),
        "settings_files": {name: file_summary(base / name) for name in LOCAL_STATE_FILES},
        "directories": {name: directory_summary(base / name) for name in LOCAL_STATE_DIRS},
        "credential_files_excluded": list(CREDENTIAL_FILES_EXCLUDED),
    }


def write_local_state_manifest(backup: Path) -> None:
    manifest = local_state_manifest(backup)
    (backup / "local_state_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_backup(codex_home: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = codex_home / "backups" / f"sync-codex-history-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)

    for name in SQLITE_BACKUP_FILES:
        src = codex_home / name
        if src.exists():
            sqlite_backup(src, backup / name)

    for name in HISTORY_BACKUP_FILES + LOCAL_STATE_FILES:
        copy_if_exists(codex_home / name, backup / name)

    for name in HISTORY_BACKUP_DIRS + LOCAL_STATE_DIRS:
        copy_if_exists(codex_home / name, backup / name)

    write_local_state_manifest(backup)
    return backup


def ensure_child_path(child: Path, parent: Path) -> None:
    child_resolved = child.resolve()
    parent_resolved = parent.resolve()
    try:
        is_child = child_resolved == parent_resolved or child_resolved.is_relative_to(parent_resolved)
    except AttributeError:
        is_child = str(child_resolved).startswith(str(parent_resolved) + os.sep)
    if not is_child:
        raise ValueError(f"Refusing to operate outside {parent_resolved}: {child_resolved}")


def replace_path_from_backup(src: Path, dst: Path, codex_home: Path) -> None:
    ensure_child_path(dst, codex_home)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def restore_local_state(codex_home: Path, backup: Path) -> dict[str, Any]:
    codex_home = codex_home.expanduser().resolve()
    backup = backup.expanduser().resolve()
    if not codex_home.exists():
        raise FileNotFoundError(f"Codex home not found: {codex_home}")
    if not backup.exists() or not backup.is_dir():
        raise FileNotFoundError(f"Backup directory not found: {backup}")

    rollback = make_backup(codex_home)
    restored: list[str] = []
    missing_from_backup: list[str] = []

    for name in LOCAL_STATE_FILES:
        src = backup / name
        if src.exists() and src.is_file():
            ensure_child_path(src, backup)
            replace_path_from_backup(src, codex_home / name, codex_home)
            restored.append(name)
        else:
            missing_from_backup.append(name)

    for name in LOCAL_STATE_DIRS:
        src = backup / name
        if src.exists() and src.is_dir():
            ensure_child_path(src, backup)
            replace_path_from_backup(src, codex_home / name, codex_home)
            restored.append(name)
        else:
            missing_from_backup.append(name)

    return {
        "codex_home": str(codex_home),
        "source_backup": str(backup),
        "rollback_dir": str(rollback),
        "restored": restored,
        "missing_from_backup": missing_from_backup,
        "credential_files_excluded": list(CREDENTIAL_FILES_EXCLUDED),
        "restart_required": True,
        "restart_hint": "Restart Codex or open a new thread so settings, skills, plugins, and pet state are reloaded.",
    }


def read_index_ids(codex_home: Path) -> set[str]:
    path = codex_home / "session_index.jsonl"
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("rb") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj.get("id"), str):
                ids.add(obj["id"])
    return ids


def rollout_file_ids(codex_home: Path) -> set[str]:
    ids: set[str] = set()
    patterns = [
        str(codex_home / "sessions" / "**" / "*.jsonl"),
        str(codex_home / "archived_sessions" / "**" / "*.jsonl"),
    ]
    for pattern in patterns:
        for path in glob.glob(pattern, recursive=True):
            match = THREAD_ID_RE.search(os.path.basename(path))
            if match:
                ids.add(match.group(0))
    return ids


def safe_source_summary(source: Any) -> str:
    if source is None:
        return ""
    text = str(source)
    if len(text) > 80:
        return text[:77] + "..."
    return text


def load_threads(codex_home: Path) -> list[dict[str, Any]]:
    db = codex_home / "state_5.sqlite"
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        table_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'threads'"
        ).fetchone()
        if not table_exists:
            return []
        available = {row["name"] for row in con.execute("PRAGMA table_info(threads)")}
        wanted = [
            "id",
            "title",
            "source",
            "model_provider",
            "cwd",
            "archived",
            "thread_source",
            "created_at",
            "updated_at",
            "rollout_path",
        ]
        select_cols = [name for name in wanted if name in available]
        if "id" not in select_cols:
            return []
        order_col = "updated_at" if "updated_at" in available else "id"
        rows = con.execute(
            f"SELECT {', '.join(select_cols)} FROM threads ORDER BY {order_col} DESC"
        ).fetchall()
    finally:
        con.close()
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = {name: None for name in wanted}
        item.update(dict(row))
        normalized.append(item)
    return normalized


def is_internal_thread(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "")
    title = str(row.get("title") or "")
    thread_source = str(row.get("thread_source") or "")
    if thread_source and thread_source != "user":
        return True
    if "subagent" in source:
        return True
    if title.startswith("The following is the Codex agent history whose request action you are assessing"):
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", default=str(default_codex_home()))
    parser.add_argument("--no-backup", action="store_true", help="Inspect only; do not create backup.")
    parser.add_argument(
        "--restore-local-state-from",
        help="Restore settings, skills, plugins, and pets from a previous backup. Credentials are never restored.",
    )
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve()
    if not codex_home.exists():
        raise SystemExit(f"Codex home not found: {codex_home}")

    if args.restore_local_state_from:
        restore_report = restore_local_state(codex_home, Path(args.restore_local_state_from))
        print(json.dumps(restore_report, ensure_ascii=False, indent=2))
        return 0

    backup = None if args.no_backup else make_backup(codex_home)
    threads = load_threads(codex_home)
    index_ids = read_index_ids(codex_home)
    file_ids = rollout_file_ids(codex_home)

    user_threads = [row for row in threads if not is_internal_thread(row)]
    internal_threads = [row for row in threads if is_internal_thread(row)]
    not_indexed = [row for row in user_threads if row["id"] not in index_ids]

    providers: dict[str, int] = {}
    for row in user_threads:
        key = str(row.get("model_provider") or "")
        providers[key] = providers.get(key, 0) + 1

    report = {
        "codex_home": str(codex_home),
        "backup_dir": str(backup) if backup else None,
        "thread_count_total": len(threads),
        "thread_count_user": len(user_threads),
        "thread_count_internal_skipped": len(internal_threads),
        "session_file_ids": len(file_ids),
        "session_index_ids": len(index_ids),
        "model_provider_counts": providers,
        "local_state": local_state_manifest(codex_home),
        "local_state_restore": {
            "supported": True,
            "restores": list(LOCAL_STATE_FILES + LOCAL_STATE_DIRS),
            "credential_files_excluded": list(CREDENTIAL_FILES_EXCLUDED),
            "command": (
                "python scripts/inspect_codex_history.py "
                f"--codex-home {json.dumps(str(codex_home), ensure_ascii=False)} "
                "--restore-local-state-from <backup-dir>"
            ),
            "restart_required_after_restore": True,
        },
        "candidate_hidden_or_unindexed_user_threads": [
            {
                "id": row["id"],
                "title": row.get("title"),
                "archived": row.get("archived"),
                "model_provider": row.get("model_provider"),
                "source": safe_source_summary(row.get("source")),
                "cwd": str(row.get("cwd") or "").replace("\\\\?\\", ""),
                "has_rollout_file": row["id"] in file_ids or Path(str(row.get("rollout_path") or "")).exists(),
                "reason": "not present in session_index.jsonl",
            }
            for row in not_indexed
        ],
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
