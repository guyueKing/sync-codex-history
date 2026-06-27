#!/usr/bin/env python3
"""Inspect local Codex history safely and create a rollback backup.

This script intentionally does not modify Codex state. Use Codex App thread
tools to fork readable hidden user threads into the current account context.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any


THREAD_ID_RE = re.compile(r"019[0-9a-f-]{32,}")


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


def make_backup(codex_home: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = codex_home / "backups" / f"sync-codex-history-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)

    for name in ("state_5.sqlite", "goals_1.sqlite", "memories_1.sqlite", "logs_2.sqlite"):
        src = codex_home / name
        if src.exists():
            sqlite_backup(src, backup / name)

    for name in ("session_index.jsonl", ".codex-global-state.json", ".codex-global-state.json.bak"):
        copy_if_exists(codex_home / name, backup / name)

    for name in ("sessions", "archived_sessions", "pets"):
        copy_if_exists(codex_home / name, backup / name)

    return backup


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
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve()
    if not codex_home.exists():
        raise SystemExit(f"Codex home not found: {codex_home}")

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
