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


class LanguagesTest(RuleTestCase):
    """markdown.languages: one document set, N ordered language variants.

    Labels are plain ASCII here because the checker only looks at link targets
    and at which entry is the bold current language.
    """

    def languages(self, **extra):
        block = {"default": "README.md", "variants": ["README.zh-CN.md", "README.ja.md"]}
        block.update(extra)
        return self.config(markdown={"globs": ["*.md"], "check_links": True, "languages": block})

    def files(self):
        return sorted(self.root.glob("*.md"))

    def switch(self, current, *others):
        return ("# Demo\n\n**%s** \xc2\xb7 " % current) + " \xc2\xb7 ".join(
            "[%s](%s)" % (name, name) for name in others
        ) + "\n"

    def test_complete_set_with_ordered_switch_lines(self):
        self.write("README.md", self.switch("English", "README.zh-CN.md", "README.ja.md").encode())
        self.write("README.zh-CN.md", self.switch("Chinese", "README.md", "README.ja.md").encode())
        self.write("README.ja.md", self.switch("Japanese", "README.md", "README.zh-CN.md").encode())
        self.assertEqual(repo_rules.Checker(self.languages()).run(self.files()).problems, [])

    def test_missing_variant_is_a_violation(self):
        self.write("README.md", self.switch("English", "README.zh-CN.md", "README.ja.md").encode())
        self.write("README.zh-CN.md", self.switch("Chinese", "README.md", "README.ja.md").encode())
        problems = "\n".join(repo_rules.Checker(self.languages()).run(self.files()).problems)
        self.assertIn("missing language variant", problems)
        self.assertIn("README.ja.md", problems)

    def test_wrong_order_is_a_violation(self):
        # ja listed before zh-CN, while the config says zh-CN then ja
        self.write("README.md", self.switch("English", "README.ja.md", "README.zh-CN.md").encode())
        self.write("README.zh-CN.md", self.switch("Chinese", "README.md", "README.ja.md").encode())
        self.write("README.ja.md", self.switch("Japanese", "README.md", "README.zh-CN.md").encode())
        problems = "\n".join(repo_rules.Checker(self.languages()).run(self.files()).problems)
        self.assertIn("switch line lists", problems)

    def test_current_language_must_be_first_and_bold(self):
        self.write("README.md", ("# Demo\n\n[ZH](README.zh-CN.md) \xc2\xb7 [JA](README.ja.md)\n").encode())
        problems = "\n".join(repo_rules.Checker(self.languages()).run(self.files()).problems)
        self.assertIn("in bold", problems)

    def test_missing_switch_line_is_a_violation(self):
        self.write("README.md", b"# Demo\n\n## Usage\n")
        problems = "\n".join(repo_rules.Checker(self.languages()).run(self.files()).problems)
        self.assertIn("no language switch line", problems)

    def test_switch_line_ignores_leading_comment(self):
        body = b"<!-- translated-from: README.md sha256:0123456789ab -->\n\n" + self.switch(
            "Chinese", "README.md", "README.ja.md"
        ).encode()
        self.write("README.md", self.switch("English", "README.zh-CN.md", "README.ja.md").encode())
        self.write("README.zh-CN.md", body)
        self.write("README.ja.md", self.switch("Japanese", "README.md", "README.zh-CN.md").encode())
        self.assertEqual(repo_rules.Checker(self.languages()).run(self.files()).problems, [])

    def test_default_must_not_be_a_variant(self):
        data = {
            "version": 1,
            "markdown": {"globs": ["*.md"], "languages": {"default": "README.md", "variants": ["README.md"]}},
        }
        with self.assertRaises(repo_rules.ConfigError):
            repo_rules.RuleConfig(self.root, data)

    def test_switch_line_can_be_disabled(self):
        self.write("README.md", b"# Demo\n\n## Usage\n")
        config = self.languages(switch_line=False)
        self.write("README.zh-CN.md", b"# Demo\n")
        self.write("README.ja.md", b"# Demo\n")
        self.assertEqual(repo_rules.Checker(config).run(self.files()).problems, [])



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


class TranslationTest(RuleTestCase):
    """markdown.translations: marker staleness, CJK wrapping, language links."""

    def translations(self, **extra):
        block = {"pairs": [["README.md", "README.zh-CN.md"]]}
        block.update(extra)
        return repo_rules.RuleConfig(
            self.root,
            {
                "version": 1,
                "markdown": {"globs": ["*.md"], "check_links": True, "bilingual_pairs": [], "translations": block},
            },
        )

    def test_marker_matches_then_reports_stale(self) -> None:
        source = b"# Title\n\nEnglish body.\n"
        digest = repo_rules.hashlib.sha256(source).hexdigest()[:12]
        self.write("README.md", source)
        self.write(
            "README.zh-CN.md",
            ("# \u6807\u9898\n\n<!-- translated-from: README.md sha256:%s -->\n" % digest).encode("utf-8"),
        )
        report = repo_rules.Checker(self.translations()).run([])
        self.assertEqual(report.problems, [])
        self.assertEqual(report.warnings, [])

        self.write("README.md", b"# Title\n\nEnglish body changed.\n")
        report = repo_rules.Checker(self.translations()).run([])
        self.assertEqual(report.problems, [])
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("translation-stale", report.warnings[0])

    def test_missing_marker_is_a_violation(self) -> None:
        self.write("README.md", b"# Title\n")
        self.write("README.zh-CN.md", "# \u6807\u9898\n".encode("utf-8"))
        report = repo_rules.Checker(self.translations()).run([])
        self.assertIn("translation", "\n".join(report.problems))

    def test_stale_can_be_promoted_to_error(self) -> None:
        self.write("README.md", b"# Title\n")
        self.write("README.zh-CN.md", b"# T\n\n<!-- translated-from: README.md sha256:000000000000 -->\n")
        report = repo_rules.Checker(self.translations(stale="error")).run([])
        self.assertIn("translation-stale", "\n".join(report.problems))

    def test_cjk_wrap_flags_break_between_characters(self) -> None:
        self.write("README.md", b"# Title\n")
        self.write(
            "README.zh-CN.md",
            "# \u6807\u9898\n\n<!-- translated-from: README.md sha256:000000000000 -->\n\n"
            "\u8fd9\u662f\u4e00\u4e2a\u5f88\u957f\u7684\u53e5\u5b50\n\u5c1a\u672a\u7ed3\u675f\u3002\n".encode("utf-8"),
        )
        report = repo_rules.Checker(self.translations(cjk_wrap=True)).run([])
        self.assertIn("cjk-wrap", "\n".join(report.problems))

        # A break after punctuation is the correct way to wrap Chinese text.
        self.write(
            "README.zh-CN.md",
            (
                "# \u6807\u9898\n\n<!-- translated-from: README.md sha256:000000000000 -->\n\n"
                "\u8fd9\u662f\u4e00\u4e2a\u5f88\u957f\u7684\u53e5\u5b50\u3002\n"
                "\u4e0b\u4e00\u53e5\u4ece\u8fd9\u91cc\u5f00\u59cb\u3002\n"
            ).encode("utf-8"),
        )
        report = repo_rules.Checker(self.translations(cjk_wrap=True)).run([])
        self.assertNotIn("cjk-wrap", "\n".join(report.problems))

    def test_lang_links_prefers_translated_sibling(self) -> None:
        self.write("README.md", b"# Title\n")
        self.write("docs/guide.md", b"# Guide\n")
        self.write("docs/guide.zh-CN.md", b"# \u6307\u5357\n")
        self.write(
            "README.zh-CN.md",
            (
                "# \u6807\u9898\n\n<!-- translated-from: README.md sha256:000000000000 -->\n\n"
                "- [English](README.md)\n"
                "- [guide](docs/guide.md)\n"
            ).encode("utf-8"),
        )
        report = repo_rules.Checker(self.translations(keep_language=True)).run([])
        joined = "\n".join(report.problems)
        self.assertIn("lang-link", joined)
        self.assertIn("docs/guide.zh-CN.md", joined)
        self.assertNotIn("README.md; use", joined)


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
