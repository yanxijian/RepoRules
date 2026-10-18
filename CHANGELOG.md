# Changelog

All notable changes to RepoRules are documented here.

## [Unreleased]

### Added

- `sync` command: refresh the vendored `scripts/repo_rules.py` (and
  `.githooks/pre-commit` with `--hook`) in a project that ran `init`;
  `--check` exits 1 when a copy is stale, so CI can detect drift.

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

[Unreleased]: https://github.com/yanxijian/RepoRules/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yanxijian/RepoRules/releases/tag/v0.1.0
