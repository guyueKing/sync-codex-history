from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect_codex_history.py"


def load_module():
    spec = importlib.util.spec_from_file_location("inspect_codex_history", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


inspect = load_module()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LocalStateBackupTests(unittest.TestCase):
    def test_backup_includes_settings_skills_plugins_and_pets_but_not_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()

            write(codex_home / ".codex-global-state.json", '{"theme":"old"}')
            write(codex_home / "config.toml", 'model = "gpt-5.4"')
            write(codex_home / "AGENTS.md", "Prefer local continuity.")
            write(codex_home / "auth.json", '{"token":"secret"}')
            write(codex_home / "skills" / "example-skill" / "SKILL.md", "---\nname: example-skill\n---\n")
            write(codex_home / "plugins" / "cache" / "example-plugin" / "plugin.json", "{}")
            write(codex_home / "pets" / "shy-miku" / "state.json", '{"mood":"happy"}')

            backup = inspect.make_backup(codex_home)

            self.assertTrue((backup / ".codex-global-state.json").exists())
            self.assertTrue((backup / "config.toml").exists())
            self.assertTrue((backup / "AGENTS.md").exists())
            self.assertTrue((backup / "skills" / "example-skill" / "SKILL.md").exists())
            self.assertTrue((backup / "plugins" / "cache" / "example-plugin" / "plugin.json").exists())
            self.assertTrue((backup / "pets" / "shy-miku" / "state.json").exists())
            self.assertTrue((backup / "local_state_manifest.json").exists())
            self.assertFalse((backup / "auth.json").exists())

    def test_restore_replaces_local_state_from_backup_and_preserves_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            backup = root / "backup"
            codex_home.mkdir()
            backup.mkdir()

            write(codex_home / "config.toml", 'model = "current"')
            write(codex_home / "auth.json", '{"token":"keep-current"}')
            write(codex_home / "skills" / "current-only" / "SKILL.md", "current")
            write(codex_home / "pets" / "current-pet" / "state.json", "current")

            write(backup / "config.toml", 'model = "previous"')
            write(backup / ".codex-global-state.json", '{"pet":"previous"}')
            write(backup / "skills" / "previous-skill" / "SKILL.md", "previous")
            write(backup / "plugins" / "cache" / "previous-plugin" / "plugin.json", "{}")
            write(backup / "pets" / "previous-pet" / "state.json", "previous")
            write(backup / "auth.json", '{"token":"must-not-copy"}')

            result = inspect.restore_local_state(codex_home, backup)

            self.assertEqual((codex_home / "config.toml").read_text(encoding="utf-8"), 'model = "previous"')
            self.assertEqual((codex_home / "auth.json").read_text(encoding="utf-8"), '{"token":"keep-current"}')
            self.assertTrue((codex_home / ".codex-global-state.json").exists())
            self.assertTrue((codex_home / "skills" / "previous-skill" / "SKILL.md").exists())
            self.assertFalse((codex_home / "skills" / "current-only").exists())
            self.assertTrue((codex_home / "plugins" / "cache" / "previous-plugin" / "plugin.json").exists())
            self.assertTrue((codex_home / "pets" / "previous-pet" / "state.json").exists())
            self.assertFalse((codex_home / "pets" / "current-pet").exists())
            self.assertTrue(Path(result["rollback_dir"]).exists())
            self.assertNotIn("auth.json", result["restored"])


if __name__ == "__main__":
    unittest.main()
