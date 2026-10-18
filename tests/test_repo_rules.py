#!/usr/bin/env python3
"""Tests for the repo-rules engine."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import repo_rules


class RuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def config(self, **overrides):
        data = {
            "version": 1,
            "skip_dirs": [".git"],
            "skip_prefixes": [],
            "skip_globs": [],
            "encoding": [],
            "width": {"globs": [], "limit": 140, "tab_width": 4},
            "forbidden": [],
            "headers": {"globs": [], "first_line": "#pragma once", "forbid_namespace_using": True},
            "versions": [],
            "changelog": None,
            "required_files": [],
            "markdown": {"globs": [], "check_links": True, "bilingual_pairs": []},
            "gitattributes": {"path": ".gitattributes", "required_patterns": []},
        }
        data.update(overrides)
        return repo_rules.RuleConfig(self.root, data)


class EncodingTest(RuleTestCase):
    def test_fix_adds_bom_and_crlf(self) -> None:
        path = self.write("src/a.cpp", b"int a;\n")
        config = self.config(encoding=[{"glob": "*.cpp", "bom": True, "eol": "crlf"}])
        report = repo_rules.Checker(config).run([path], fix=True)
        data = path.read_bytes()
        self.assertTrue(data.startswith(repo_rules.BOM))
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
        self.assertEqual(len(report.problems), 0)
        self.assertEqual(len(report.fixed), 1)

    def test_fix_removes_bom_and_crlf_for_lf_rule(self) -> None:
        path = self.write("tool.py", repo_rules.BOM + b"print(1)\r\n")
        config = self.config(encoding=[{"glob": "*.py", "bom": False, "eol": "lf"}])
        repo_rules.Checker(config).run([path], fix=True)
        data = path.read_bytes()
        self.assertFalse(data.startswith(repo_rules.BOM))
        self.assertNotIn(b"\r\n", data)

    def test_reports_without_fix(self) -> None:
        path = self.write("a.cpp", b"int a;\n")
        config = self.config(encoding=[{"glob": "*.cpp", "bom": True, "eol": "crlf"}])
        report = repo_rules.Checker(config).run([path], fix=False)
        text = " ".join(report.problems)
        self.assertIn("missing UTF-8 BOM", text)
        self.assertIn("bare LF", text)


class ContentRulesTest(RuleTestCase):
    def test_width_and_forbidden_and_header(self) -> None:
        path = self.write("a.h", b"using namespace std;\n" + b"x" * 141 + b"\n")
        config = self.config(
            width={"globs": ["*.h"], "limit": 140, "tab_width": 4},
            forbidden=[{"id": "no-using", "globs": ["*.h"], "pattern": "^using namespace", "message": "qualified names"}],
            headers={"globs": ["*.h"], "first_line": "#pragma once", "forbid_namespace_using": True},
        )
        report = repo_rules.Checker(config).run([path])
        text = "\n".join(report.problems)
        self.assertIn("width", text)
        self.assertIn("header", text)
        self.assertIn("no-using", text)

    def test_version_sync(self) -> None:
        self.write("CMakeLists.txt", b"project(demo VERSION 1.2.3 LANGUAGES CXX)\n")
        self.write("version.h", b"#define DEMO_VERSION 1.2.3\n")
        config = self.config(
            versions=[
                {
                    "id": "demo",
                    "sources": [
                        {"path": "CMakeLists.txt", "pattern": r"VERSION\s+(\d+)\.(\d+)\.(\d+)"},
                        {"path": "version.h", "pattern": r"DEMO_VERSION\s+(\d+)\.(\d+)\.(\d+)"},
                    ],
                }
            ]
        )
        self.assertEqual(repo_rules.Checker(config).run([]).problems, [])
        self.write("version.h", b"#define DEMO_VERSION 1.2.4\n")
        report = repo_rules.Checker(config).run([])
        self.assertIn("version", "\n".join(report.problems))

    def test_changelog_and_required(self) -> None:
        self.write("LICENSE", b"MIT\n")
        self.write("CHANGELOG.md", b"## [Unreleased]\n\n[Unreleased]: https://example.com\n")
        config = self.config(
            changelog={"path": "CHANGELOG.md", "require": "## [Unreleased]", "link_definitions": True},
            required_files=["LICENSE", "CHANGELOG.md"],
        )
        self.assertEqual(repo_rules.Checker(config).run([]).problems, [])
        self.write("CHANGELOG.md", b"## [Unreleased]\n")
        self.assertIn("changelog", "\n".join(repo_rules.Checker(config).run([]).problems))


class DocumentationTest(RuleTestCase):
    def test_links_and_bilingual_pair(self) -> None:
        self.write("README.md", b"# Demo\n\n[English](README.en.md)\n")
        self.write("README.en.md", b"# Demo\n\n[\xe4\xb8\xad\xe6\x96\x87](README.md)\n")
        config = self.config(
            markdown={"globs": ["*.md"], "check_links": True, "bilingual_pairs": [["README.md", "README.en.md"]]}
        )
        self.assertEqual(repo_rules.Checker(config).run(sorted(self.root.glob("*.md"))).problems, [])

        self.write("README.md", b"# Demo\n\n[missing](NOPE.md)\n")
        report = repo_rules.Checker(config).run(sorted(self.root.glob("*.md")))
        self.assertIn("links", "\n".join(report.problems))

    def test_skip_globs_silences_markdown_links(self) -> None:
        # A file that points into a submodule cannot resolve on a CI checkout
        # without submodules; skip_globs must silence the link check for it.
        self.write("docs/generated.md", b"# Generated\n\n[pdfium](../pdfium/docs/x.md)\n")
        self.write("README.md", b"# Demo\n\n[missing](NOPE.md)\n")
        config = self.config(markdown={"globs": ["*.md"], "check_links": True}, skip_globs=["docs/generated.md"])
        files = sorted(self.root.rglob("*.md"))
        problems = "\n".join(repo_rules.Checker(config).run(files).problems)
        self.assertNotIn("docs/generated.md", problems)
        self.assertIn("README.md", problems)


class SyncTest(RuleTestCase):
    def args(self, **overrides):
        values = {
            "root": str(self.root),
            "dest": "scripts/repo_rules.py",
            "source": str(Path(repo_rules.__file__).resolve()),
            "hook": False,
            "check": False,
        }
        values.update(overrides)
        return repo_rules.argparse.Namespace(**values)

    def test_sync_copies_checker_and_hook(self) -> None:
        self.assertEqual(repo_rules.command_sync(self.args(hook=True)), 0)
        vendored = self.root / "scripts" / "repo_rules.py"
        self.assertEqual(vendored.read_bytes(), Path(repo_rules.__file__).read_bytes())
        self.assertTrue((self.root / ".githooks" / "pre-commit").is_file())
        self.assertEqual(repo_rules.command_sync(self.args(hook=True, check=True)), 0)

        vendored.write_bytes(b"# stale\n")
        self.assertEqual(repo_rules.command_sync(self.args(check=True)), 1)
        self.assertEqual(repo_rules.command_sync(self.args()), 0)
        self.assertEqual(vendored.read_bytes(), Path(repo_rules.__file__).read_bytes())

    def test_sync_rejects_missing_target(self) -> None:
        self.assertEqual(repo_rules.command_sync(self.args(root=str(self.root / "nope"))), 2)


class HookTemplateTest(unittest.TestCase):
    def test_embedded_hook_matches_template_file(self) -> None:
        template = Path(repo_rules.__file__).resolve().parent / "templates" / "githooks" / "pre-commit"
        self.assertEqual(template.read_text(encoding="utf-8"), repo_rules.PRECOMMIT_HOOK)


class PresetTest(unittest.TestCase):
    def test_powershell_scripts_require_bom(self) -> None:
        presets = Path(__file__).resolve().parent.parent / "presets"
        for path in sorted(presets.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for rule in data.get("encoding", []):
                if rule.get("glob") == "*.ps1":
                    self.assertTrue(
                        rule.get("bom"),
                        "%s must require a UTF-8 BOM for *.ps1" % path.name,
                    )


class InitTest(RuleTestCase):
    def test_init_writes_config_tool_and_templates(self) -> None:
        args = repo_rules.argparse.Namespace(
            root=str(self.root), preset="python-tool", force=False, no_tool=False
        )
        self.assertEqual(repo_rules.command_init(args), 0)
        self.assertTrue((self.root / "repo-rules.json").is_file())
        self.assertTrue((self.root / "scripts" / "repo_rules.py").is_file())
        self.assertTrue((self.root / ".githooks" / "pre-commit").is_file())
        self.assertTrue((self.root / ".github" / "workflows" / "hygiene.yml").is_file())

        loaded = json.loads((self.root / "repo-rules.json").read_text(encoding="utf-8"))
        self.assertEqual(loaded["version"], 1)


if __name__ == "__main__":
    unittest.main()
