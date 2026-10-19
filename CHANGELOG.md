# Changelog

All notable changes to RepoRules are documented here.

## [Unreleased]

### Added

- `comments.english`: code comments must be English. Flags Han, Kana, Hangul, CJK
  punctuation and fullwidth forms inside comments; quotations and data samples opt
  out with the `allow_marker` token (`cjk-ok`) or a file glob in `allow_files`.
  Only unambiguous comment shapes are read (`//` / `/* */`, `#`, `REM` / `::`), so a
  `#define ... L"中文"` preprocessor line and an `echo "中文"` string literal are
  never flagged.
- `markdown.languages.stale`: `off` (default) / `warning` / `error`. When on, every
  language variant must carry `<!-- translated-from: <default> sha256:<12> -->`,
  and a changed default file reports `language-stale` with both hashes. The
  switch-line check proves the variants know about each other; this proves they
  still say the same thing. `warning` keeps the build green on purpose (translating
  is real work); `error` is for repos that translate in the same change.
- `markdown.languages`: one document set with N ordered language variants.
  Checks that every variant exists, that each file's language switch line starts
  with the current language in bold, and that the line links to the other
  variants in the configured order. `bilingual_pairs` only proved two files knew
  about each other; this pins completeness and order for sets larger than two.
- `markdown.translations`: optional checks for a maintained translated set -
  the `<!-- translated-from: <file> sha256:<12> -->` marker and staleness
  (report-only by default), CJK line wrapping (`cjk_wrap`), and "a translation
  links to its translated siblings" (`keep_language`). Off unless configured.
- `docs/ci-scheduling.md`: how to scope a build workflow so documentation-only
  changes do not start the compile/test pipeline. Covers the positive `paths:`
  allowlist (recommended), the `paths-ignore` alternative and its test-fixture
  trap, the split of duties with `hygiene.yml`, the branch-protection caveat,
  and a job-level gate for the case where a required check must stay.

### Fixed

- `skip_globs` now also silences Markdown link checking. The per-file rules
  honoured it, but `_check_markdown()` received the unfiltered file list, so a
  document linking into a submodule (absent on a CI checkout) failed even when
  listed in `skip_globs`.

## [0.2.0] - 2026-10-19

### Added

- `sync` command: refresh the vendored `scripts/repo_rules.py` (and
  `.githooks/pre-commit` with `--hook`) in a project that ran `init`;
  `--check` exits 1 when a copy is stale, so CI can detect drift.
- The pre-commit hook body is embedded in `repo_rules.py`, so `sync --hook`
  also works from a vendored copy where `templates/` does not exist.

### Changed

- `cpp-windows` / `cpp-library` presets now require a UTF-8 BOM for `*.ps1`:
  Windows PowerShell 5.1 decodes BOM-less scripts as ANSI, so non-ASCII text
  turns into mojibake and may fail to parse. `docs/configuration.md` documents
  the requirement, and a preset test guards it.
- Pre-commit hook now probes each Python candidate (`python3`, `python`, `py`)
  with `-c 'import sys'` before using it, so the Windows Store `python3` stub
  no longer breaks commits.

## [0.1.0] - 2026-10-18

### Added

- Configurable checker for encoding/BOM/line endings, width, forbidden patterns,
  header conventions, version sync, changelog shape, required files, Markdown
  links and bilingual pairs.
- `check`, `fix`, `init` and `list-presets` commands.
- Built-in `cpp-windows`, `cpp-library` and `python-tool` presets.
- Pre-commit hook and hygiene workflow templates.
- Unit tests and self-checking configuration.

[Unreleased]: https://github.com/yanxijian/RepoRules/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yanxijian/RepoRules/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yanxijian/RepoRules/releases/tag/v0.1.0
