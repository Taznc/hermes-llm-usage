import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


API_PATH = Path(__file__).parents[1] / "plugins" / "llm-usage" / "dashboard" / "plugin_api.py"


class _Router:
    def get(self, _path):
        return lambda fn: fn


if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")
    setattr(fastapi_stub, "APIRouter", _Router)
    sys.modules["fastapi"] = fastapi_stub

spec = importlib.util.spec_from_file_location("llm_usage_plugin_api", API_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load plugin API module")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


GROK_1_0_USAGE = """
Weekly limit (SuperGrok)
██░░░░░░░░░░░░░░░░░░░░░░░░░░░░  6%
Resets: September 18, 20:50
"""

GROK_1_0_USAGE_BOXED = """
                          │  Context usage  Usage limit  Session info                                                     │
                          │  Weekly limit (SuperGrok)                                                                     │
                          │                                                                                               │
                          │  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░  8%                                                           │
                          │  Resets: September 18, 20:50                                                                  │
                          │  Session usage: no model calls yet in this session.                                           │
"""


class GrokUsageParseTests(TestCase):
    def test_parse_grok_1_0_modal_percent_on_bar_line(self):
        windows = api.parse_grok_usage(GROK_1_0_USAGE)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["id"], "weekly")
        self.assertEqual(windows[0]["used_pct"], 6.0)
        self.assertEqual(windows[0]["reset_label"], "September 18, 20:50")
        self.assertIn("SuperGrok", windows[0]["label"])

    def test_parse_grok_1_0_modal_inside_box_drawing(self):
        windows = api.parse_grok_usage(GROK_1_0_USAGE_BOXED)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["id"], "weekly")
        self.assertEqual(windows[0]["used_pct"], 8.0)
        self.assertEqual(windows[0]["reset_label"], "September 18, 20:50")
        self.assertIn("SuperGrok", windows[0]["label"])

    def test_parse_grok_0_2_weekly_limit_same_line(self):
        text = "Weekly limit: 12%\nNext reset: August 3, 07:22\n"
        windows = api.parse_grok_usage(text)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["used_pct"], 12.0)
        self.assertEqual(windows[0]["reset_label"], "August 3, 07:22")
        self.assertEqual(windows[0]["label"], "Weekly Grok")

    def test_parse_grok_weekly_limit_left_inverts_to_used(self):
        text = "Weekly limit left: 42%\nNext reset: August 3, 07:22\n"
        windows = api.parse_grok_usage(text)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["used_pct"], 58.0)
        self.assertEqual(windows[0]["reset_label"], "August 3, 07:22")


class WorkdirTests(TestCase):
    def test_workdir_prefers_lowercase_projects_hermes_llm_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project = home / "projects" / "hermes-llm-usage"
            project.mkdir(parents=True)
            with patch.object(api.Path, "home", return_value=home):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("HERMES_LLM_USAGE_WORKDIR", None)
                    self.assertEqual(api._workdir(), project)

    def test_workdir_uses_lowercase_projects_tree_instead_of_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            projects = home / "projects"
            projects.mkdir()
            with patch.object(api.Path, "home", return_value=home):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("HERMES_LLM_USAGE_WORKDIR", None)
                    self.assertEqual(api._workdir(), projects)


CLAUDE_TRUST_DIALOG = """
Do you trust the contents of this folder?

❯ 1. Yes, I trust this folder
  2. No, exit
"""

CLAUDE_RENDERER_DIALOG = """
Try the new fullscreen renderer?

❯ 1. Yes, try it
  2. Not now
"""

CLAUDE_COMPOSER = """
Welcome back

  /help for help

❯ Try "explain this codebase"
"""


class ClaudeReadyDetectionTests(TestCase):
    def test_trust_dialog_glyph_is_not_ready(self):
        self.assertFalse(api._claude_pane_is_ready(CLAUDE_TRUST_DIALOG))

    def test_fullscreen_renderer_dialog_is_not_ready(self):
        self.assertFalse(api._claude_pane_is_ready(CLAUDE_RENDERER_DIALOG))

    def test_composer_prompt_is_ready(self):
        self.assertTrue(api._claude_pane_is_ready(CLAUDE_COMPOSER))

    def test_trust_dialog_dismisses_with_enter(self):
        self.assertEqual(api._claude_first_run_dismiss_keys(CLAUDE_TRUST_DIALOG), ["Enter"])

    def test_renderer_dialog_dismisses_with_not_now(self):
        self.assertEqual(
            api._claude_first_run_dismiss_keys(CLAUDE_RENDERER_DIALOG),
            ["2", "Enter"],
        )

    def test_composer_has_no_dismiss_keys(self):
        self.assertIsNone(api._claude_first_run_dismiss_keys(CLAUDE_COMPOSER))


if __name__ == "__main__":
    import unittest

    unittest.main()
