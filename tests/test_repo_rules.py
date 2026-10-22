#!/usr/bin/env python3
"""Tests for the repo-rules engine."""

from __future__ import annotations

import json
import hashlib
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

    # --- stale: each variant records the default file's hash -----------------

    def marker(self, digest: str) -> bytes:
        return ("<!-- translated-from: README.md sha256:%s -->\n\n" % digest).encode()

    def stale_set(self) -> str:
        readme = self.switch("English", "README.zh-CN.md", "README.ja.md").encode()
        self.write("README.md", readme)
        digest = hashlib.sha256(readme).hexdigest()[:12]
        for name, current, others in (
            ("README.zh-CN.md", "Chinese", ("README.md", "README.ja.md")),
            ("README.ja.md", "Japanese", ("README.md", "README.zh-CN.md")),
        ):
            self.write(name, self.marker(digest) + self.switch(current, *others).encode())
        return digest

    def test_stale_markers_matching_the_source_are_clean(self):
        self.stale_set()
        report = repo_rules.Checker(self.languages(stale="warning")).run(self.files())
        self.assertEqual(report.problems, [])
        self.assertEqual(report.warnings, [])

    def test_stale_marker_missing_is_a_violation(self):
        self.stale_set()
        self.write("README.ja.md", self.switch("Japanese", "README.md", "README.zh-CN.md").encode())
        problems = "\n".join(repo_rules.Checker(self.languages(stale="warning")).run(self.files()).problems)
        self.assertIn("no `<!-- translated-from: README.md sha256:... -->` marker", problems)

    def test_changed_source_warns_but_stays_green(self):
        self.stale_set()
        self.write("README.md", self.switch("English", "README.zh-CN.md", "README.ja.md").encode() + b"\nExtra line.\n")
        report = repo_rules.Checker(self.languages(stale="warning")).run(self.files())
        self.assertEqual(report.problems, [])
        self.assertTrue(any("language-stale" in warning for warning in report.warnings))

    def test_changed_source_fails_when_stale_is_error(self):
        self.stale_set()
        self.write("README.md", self.switch("English", "README.zh-CN.md", "README.ja.md").encode() + b"\nExtra line.\n")
        problems = "\n".join(repo_rules.Checker(self.languages(stale="error")).run(self.files()).problems)
        self.assertIn("[language-stale]", problems)

    def test_stale_off_ignores_markers(self):
        self.stale_set()
        self.write("README.md", self.switch("English", "README.zh-CN.md", "README.ja.md").encode() + b"\nExtra line.\n")
        report = repo_rules.Checker(self.languages(stale="off")).run(self.files())
        self.assertEqual(report.problems, [])
        self.assertEqual(report.warnings, [])

    def test_stale_must_be_a_known_mode(self):
        data = {
            "version": 1,
            "markdown": {
                "globs": ["*.md"],
                "languages": {"default": "README.md", "variants": ["README.zh-CN.md"], "stale": "sometimes"},
            },
        }
        with self.assertRaises(repo_rules.ConfigError):
            repo_rules.RuleConfig(self.root, data)



class CommentLanguageTest(RuleTestCase):
    """comments.english: code comments are English; quotes may opt out per line."""

    def comments(self, **extra):
        block = {"english": True}
        block.update(extra)
        return self.config(comments=block)

    def problems(self, config=None):
        return "\n".join(
            repo_rules.Checker(config or self.comments()).run(sorted(self.root.glob("*.*"))).problems
        )

    def test_chinese_shell_comment_is_a_violation(self):
        self.write("run.sh", "# 部署脚本\nset -e\n".encode())
        self.assertIn("[comments]", self.problems())

    def test_english_comments_pass(self):
        self.write("run.sh", b"# Deploy script\nset -e\n")
        self.assertEqual(self.problems(), "")

    def test_cjk_in_a_string_literal_is_not_a_comment(self):
        self.write("run.sh", 'echo "部署完成"\n'.encode())
        self.assertEqual(self.problems(), "")

    def test_c_preprocessor_line_is_not_a_comment(self):
        self.write("demo.h", '#define LABEL L"中文"\n'.encode())
        self.assertEqual(self.problems(), "")

    def test_chinese_cpp_line_and_block_comments_are_violations(self):
        self.write("demo.cpp", "// 说明\nint x;\n/* 块注释 */\n".encode())
        report = repo_rules.Checker(self.comments()).run(sorted(self.root.glob("*.*")))
        self.assertEqual(sum("[comments]" in problem for problem in report.problems), 2)

    def test_allow_marker_silences_one_line(self):
        self.write("demo.cpp", '/// Design doc "命中规则"  // cjk-ok\n'.encode())
        self.assertEqual(self.problems(), "")

    def test_allow_files_skips_the_whole_file(self):
        self.write("demo.cpp", "// 说明\n".encode())
        self.assertEqual(self.problems(self.comments(allow_files=["demo.cpp"])), "")

    def test_english_false_disables_the_rule(self):
        self.write("run.sh", "# 部署脚本\n".encode())
        self.assertEqual(self.problems(self.comments(english=False)), "")


class CommitMessageTest(RuleTestCase):
    """commit_message.english: the subject and body are English."""

    def message_file(self, text: str) -> Path:
        path = self.root / "COMMIT_EDITMSG"
        path.write_bytes(text.encode("utf-8"))
        return path

    def run_check(self, text: str, english: bool = True) -> int:
        self.write(
            "repo-rules.json",
            json.dumps({"version": 1, "commit_message": {"english": english}}).encode(),
        )
        args = repo_rules.argparse.Namespace(
            message_file=str(self.message_file(text)), config="repo-rules.json", root=str(self.root)
        )
        return repo_rules.command_check_msg(args)

    def test_chinese_subject_is_rejected(self):
        self.assertEqual(self.run_check("新增四语言 README\n"), 1)

    def test_english_message_passes(self):
        self.assertEqual(self.run_check("Add the four-language README\n\nBody in English.\n"), 0)

    def test_marker_allows_a_quotation(self):
        self.assertEqual(self.run_check('Quote "命中规则" from the design doc (cjk-ok)\n'), 0)

    def test_disabled_flag_accepts_any_language(self):
        self.assertEqual(self.run_check("新增四语言 README\n", english=False), 0)


class TranslationCoverTest(RuleTestCase):
    """markdown.translations.cover / untracked: no silent new document, no silent translation."""

    def build(self, **translations):
        block = {"pairs": [], "marker": "translated-from:"}
        block.update(translations)
        config = self.config(markdown={"globs": ["*.md"], "translations": block})
        return repo_rules.Checker(config)

    def files(self, *names):
        for name in names:
            self.write(name, b"# Doc\n")
        return sorted(self.root.rglob("*.md"))

    def test_complete_cover_is_clean(self):
        paths = self.files("docs/zh/a.md", "docs/en/a.md")
        report = self.build(cover=[{"from": "docs/zh", "to": "docs/en"}]).run(paths)
        self.assertEqual(report.problems, [])

    def test_missing_translation_is_an_error(self):
        paths = self.files("docs/zh/a.md", "docs/en/a.md", "docs/zh/b.md")
        report = self.build(cover=[{"from": "docs/zh", "to": "docs/en"}]).run(paths)
        self.assertTrue(any("translation-cover" in problem and "b.md" in problem for problem in report.problems))

    def test_ignore_records_a_deliberate_gap(self):
        paths = self.files("docs/zh/a.md", "docs/en/a.md", "docs/zh/b.md")
        report = self.build(cover=[{"from": "docs/zh", "to": "docs/en", "ignore": ["b.md"]}]).run(paths)
        self.assertEqual(report.problems, [])

    def test_missing_can_be_a_warning(self):
        paths = self.files("docs/zh/a.md", "docs/en/a.md", "docs/zh/b.md")
        report = self.build(cover=[{"from": "docs/zh", "to": "docs/en", "missing": "warning"}]).run(paths)
        self.assertEqual(report.problems, [])
        self.assertTrue(any("translation-cover" in warning for warning in report.warnings))

    def marker(self, source: str) -> bytes:
        return ("<!-- translated-from: %s sha256:0123456789ab -->\n# Doc\n" % source).encode()

    def test_unpaired_english_document_is_not_flagged(self):
        self.write("docs/zh/a.md", b"# Doc\n")
        self.write("docs/en/a.md", self.marker("docs/zh/a.md"))
        self.write("docs/en/only-english.md", b"# Doc\n")
        paths = sorted(self.root.rglob("*.md"))
        report = self.build(
            pairs=[["docs/zh/a.md", "docs/en/a.md"]],
            cover=[{"from": "docs/zh", "to": "docs/en"}],
            untracked=True,
        ).run(paths)
        self.assertEqual(report.problems, [])

    def test_unregistered_translation_is_flagged(self):
        self.write("docs/zh/a.md", b"# Doc\n")
        self.write("docs/en/a.md", self.marker("docs/zh/a.md"))
        self.write("docs/zh/b.md", b"# Doc\n")
        self.write("docs/en/b.md", self.marker("docs/zh/b.md"))
        paths = sorted(self.root.rglob("*.md"))
        report = self.build(
            pairs=[["docs/zh/a.md", "docs/en/a.md"]],
            cover=[{"from": "docs/zh", "to": "docs/en"}],
            untracked=True,
        ).run(paths)
        self.assertTrue(
            any("translation-untracked" in problem and "docs/en/b.md" in problem for problem in report.problems)
        )
        self.assertFalse(
            any("translation-untracked" in problem and "docs/en/a.md" in problem for problem in report.problems)
        )

    def test_untracked_also_covers_suffixed_translations(self):
        paths = self.files("README.md", "README.zh-CN.md")
        report = self.build(pairs=[], untracked=True).run(paths)
        self.assertTrue(any("translation-untracked" in problem for problem in report.problems))


class ReadmeBadgesTest(RuleTestCase):
    """readme_badges: shields sit under the title, above the prose."""

    CI = "[![CI](https://github.com/o/r/actions/workflows/ci.yml/badge.svg)](https://github.com/o/r/actions/workflows/ci.yml)"
    LICENSE = "[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)"

    def build(self, minimum=2, required=None):
        self.write(
            "repo-rules.json",
            json.dumps(
                {
                    "version": 1,
                    "readme_badges": {"files": ["README.md"], "min": minimum, "require": required or []},
                }
            ).encode(),
        )
        return repo_rules.RuleConfig.load(self.root, "repo-rules.json")

    def problems(self, config):
        files = sorted(self.root.glob("README*.md"))
        return "\n".join(repo_rules.Checker(config).run(files).problems)

    def test_two_badges_under_the_language_line_pass(self):
        self.write(
            "README.md",
            ("# Demo\n\n**English** · [中文](README.zh-CN.md)\n\n%s\n%s\n\nProse.\n" % (self.CI, self.LICENSE)).encode(),
        )
        self.assertEqual(self.problems(self.build()), "")

    def test_single_language_readme_needs_no_switch_line(self):
        self.write("README.md", ("# Demo\n\n%s\n%s\n\nProse.\n" % (self.CI, self.LICENSE)).encode())
        self.assertEqual(self.problems(self.build()), "")

    def test_no_badge_block_is_a_violation(self):
        self.write("README.md", b"# Demo\n\nJust prose.\n")
        self.assertIn("no badge block", self.problems(self.build()))

    def test_badges_after_the_first_paragraph_are_not_at_the_top(self):
        self.write("README.md", ("# Demo\n\nProse first.\n\n%s\n%s\n" % (self.CI, self.LICENSE)).encode())
        self.assertIn("no badge block", self.problems(self.build()))

    def test_too_few_badges_is_a_violation(self):
        self.write("README.md", ("# Demo\n\n%s\n\nProse.\n" % self.CI).encode())
        self.assertIn("expected at least 2", self.problems(self.build()))

    def test_missing_required_badge_is_a_violation(self):
        self.write("README.md", ("# Demo\n\n%s\n%s\n\nProse.\n" % (self.CI, self.LICENSE)).encode())
        self.assertEqual(self.problems(self.build(required=["img.shields.io/badge/License", "actions/workflows/"])), "")
        problems = self.problems(self.build(minimum=1, required=["img.shields.io/badge/Python"]))
        self.assertIn("missing required badge: img.shields.io/badge/Python", problems)

    def test_the_same_badge_twice_is_a_violation(self):
        self.write("README.md", ("# Demo\n\n%s\n%s\n%s\n\nProse.\n" % (self.CI, self.LICENSE, self.CI)).encode())
        self.assertIn("the same badge appears 2 times", self.problems(self.build()))


class AboutTest(RuleTestCase):
    """about: one pipe, and the left side is the language the README defaults to."""

    def check(self, description: str, order: str = "en-zh") -> str:
        self.write(
            "repo-rules.json",
            json.dumps(
                {"version": 1, "about": {"description": description, "order": order}}
            ).encode(),
        )
        config = repo_rules.RuleConfig.load(self.root, "repo-rules.json")
        return "\n".join(repo_rules.Checker(config).run([]).problems)

    def test_english_first_is_clean(self):
        self.assertEqual(self.check("Header-only recursive mutex | 单头文件可重入锁"), "")

    def test_chinese_first_is_clean_when_declared(self):
        self.assertEqual(self.check("聚合仓库 | Aggregation meta-repo", order="zh-en"), "")

    def test_wrong_order_is_a_violation(self):
        problems = self.check("单头文件可重入锁 | Header-only recursive mutex")
        self.assertIn("left side must be English", problems)

    def test_missing_pipe_is_a_violation(self):
        self.assertIn("exactly one pipe", self.check("just one language"))

    def test_unknown_order_is_rejected(self):
        self.write("repo-rules.json", json.dumps({"version": 1, "about": {"order": "fr-en"}}).encode())
        with self.assertRaises(repo_rules.ConfigError):
            repo_rules.RuleConfig.load(self.root, "repo-rules.json")


class ActionsTest(RuleTestCase):
    """actions: every workflow must use the configured major version."""

    WORKFLOW = """name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@%s
      - uses: actions/cache@%s
"""

    def run_check(self, checkout: str, cache: str = "v6", **actions) -> str:
        path = self.write(
            ".github/workflows/ci.yml", (self.WORKFLOW % (checkout, cache)).encode("utf-8")
        )
        settings = {"require": {"actions/checkout": "v7", "actions/cache": "v6"}}
        settings.update(actions)
        config = self.config(actions=settings)
        return "\n".join(repo_rules.Checker(config).run([path]).problems)

    def test_required_major_passes(self):
        self.assertEqual(self.run_check("v7"), "")

    def test_patch_tag_of_the_same_major_passes(self):
        self.assertEqual(self.run_check("v7.0.1"), "")

    def test_old_major_is_reported(self):
        self.assertIn("actions/checkout@v4, expected @v7", self.run_check("v4"))

    def test_sha_pin_is_accepted_by_default(self):
        self.assertEqual(self.run_check("11d5960a326750d5838078e36cf38b85af677262"), "")

    def test_sha_pin_is_reported_when_not_allowed(self):
        problems = self.run_check("11d5960a326750d5838078e36cf38b85af677262", allow_sha=False)
        self.assertIn("pinned by a commit SHA", problems)

    def test_unlisted_action_is_ignored(self):
        self.assertEqual(self.run_check("v7"), "")

    def test_listed_action_with_a_wrong_version_is_reported(self):
        self.assertIn("actions/cache@v1, expected @v6", self.run_check("v7", cache="v1"))


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
