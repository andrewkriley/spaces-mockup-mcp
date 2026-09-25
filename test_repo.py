#!/usr/bin/env python3
"""Repo contract: venv, Ruff lint, and GitHub CI. No live network."""

from __future__ import annotations

import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class VenvAndLintContractTest(unittest.TestCase):
    def test_dev_requirements_pin_ruff(self):
        text = (HERE / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn("ruff==", text)
        self.assertNotIn("pylint", text.lower())

    def test_pyproject_configures_ruff(self):
        text = (HERE / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.ruff]", text)
        self.assertIn("target-version", text)
        self.assertIn("line-length", text)

    def test_gitignore_covers_python_and_secrets(self):
        text = (HERE / ".gitignore").read_text(encoding="utf-8")
        for needle in (
            ".venv/",
            "__pycache__/",
            ".env",
            "!.env.example",
            ".ruff_cache/",
            ".coverage",
            "htmlcov/",
            "dist/",
            ".idea/",
            ".DS_Store",
        ):
            self.assertIn(needle, text, needle)

    def test_setup_script_creates_venv(self):
        script = (HERE / "scripts" / "setup-venv.sh").read_text(encoding="utf-8")
        self.assertIn("python3 -m venv .venv", script)
        self.assertIn("requirements-dev.txt", script)
        self.assertIn("ruff", script)

    def test_run_prefers_venv_python(self):
        text = (HERE / "run.sh").read_text(encoding="utf-8")
        self.assertIn(".venv/bin/python", text)
        self.assertNotIn(":-local-dev", text)
        self.assertIn("MCP_BEARER_TOKEN is required", text)

    def test_makefile_has_lint_and_test(self):
        text = (HERE / "Makefile").read_text(encoding="utf-8")
        self.assertIn("check .", text)
        self.assertIn("format --check", text)
        self.assertIn("test_server.py", text)
        self.assertIn("test_repo.py", text)


class ReadmeContractTest(unittest.TestCase):
    def test_readme_is_a_short_connect_guide(self):
        text = (HERE / "README.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 120, len(lines))
        self.assertIn("https://spaces-mockup.apps.andrewriley.info", text)
        self.assertIn("http://127.0.0.1:8080/mcp", text)
        self.assertIn("MCP_BEARER_TOKEN", text)
        self.assertIn("not `local-dev`", text)
        self.assertIn("another spaces-mockup", text)
        self.assertIn("## Self-host", text)
        self.assertIn("## Demo server", text)
        self.assertLess(text.index("## Self-host"), text.index("## Demo server"))
        self.assertIn("LISTEN", text)
        self.assertEqual(text.count("```json"), 2, text.count("```json"))
        self.assertEqual(text.count('"mcpServers"'), 2)
        self.assertNotIn("claude mcp add-json", text)
        self.assertNotIn("Claude Desktop", text)
        self.assertNotIn("<tokengoeshere>", text)
        self.assertNotIn("spaces-ghost", text)
        self.assertNotIn("Dockerfile", text)
        self.assertNotIn("docker compose", text)
        self.assertNotIn("make ", text)
        self.assertNotIn("Makefile", text)
        self.assertIn("python3 server.py", text)
        self.assertIn("./run.sh", text)
        self.assertIn("--stdio", text)
        self.assertIn("does not use a bearer", text.lower())
        self.assertIn("docs/lab-guide.md", text)


class LabGuideContractTest(unittest.TestCase):
    def test_lab_guide_maps_data_and_how_to_connect(self):
        text = (HERE / "docs" / "lab-guide.md").read_text(encoding="utf-8")
        self.assertIn("# Lab guide", text)
        self.assertIn("## Data sources", text)
        self.assertIn("| Source |", text)
        for source in (
            "Locations",
            "Workspaces",
            "Workspace metrics",
            "RoomOS devices",
            "Device events",
            "Issue catalog",
            "Product lifecycle",
            "Device configuration",
            "Firehose EventRecords",
        ):
            self.assertIn(source, text, source)
        for tool in (
            "location_search",
            "workspace_search",
            "workspace_metrics",
            "workspace_aggregated_capacity_utilization",
            "device_search",
            "device_configuration_diff",
            "firehose_events",
            "firehose_latest",
        ):
            self.assertIn(f"`{tool}`", text, tool)
        for event in (
            "SPACE_OCCUPANCY",
            "DEVICE_LOCATION_UPDATE",
            "WEBEX_TELEMETRY",
            "KEEP_ALIVE",
        ):
            self.assertIn(event, text, event)
        self.assertIn("ws-board", text)
        self.assertIn("locationId", text)
        self.assertIn("workspaceId", text)
        self.assertIn("deviceId", text)
        self.assertIn("@mockup.example", text)
        self.assertIn("Australia/Sydney", text)
        self.assertIn("## Self-host", text)
        self.assertIn("## Demo server", text)
        self.assertLess(text.index("## Self-host"), text.index("## Demo server"))
        self.assertIn("http://127.0.0.1:8080/mcp", text)
        self.assertIn("https://spaces-mockup.apps.andrewriley.info/mcp", text)
        self.assertIn("MCP_BEARER_TOKEN", text)
        self.assertIn("${env:MCP_BEARER_TOKEN}", text)
        self.assertIn("## Configure from Claude or Cursor", text)
        self.assertIn("## Suggested prompts", text)
        self.assertIn("## Building with other apps", text)
        self.assertIn("not a live cisco api", text.lower())
        self.assertNotIn("local-dev", text)
        self.assertNotIn("<tokengoeshere>", text)
        self.assertNotIn("spaces-ghost", text)
        self.assertNotIn("WEBEX_TOKEN", text)


class CiWorkflowTest(unittest.TestCase):
    def test_ci_runs_lint_and_tests_in_venv(self):
        text = (HERE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("python3 -m venv .venv", text)
        self.assertIn("requirements-dev.txt", text)
        self.assertIn("ruff check", text)
        self.assertIn("ruff format --check", text)
        self.assertIn("test_server.py", text)
        self.assertIn("test_repo.py", text)
        self.assertIn('python-version: "3.12"', text)

    def test_legacy_test_only_workflow_removed(self):
        self.assertFalse((HERE / ".github" / "workflows" / "test.yml").exists())


if __name__ == "__main__":
    unittest.main()
