# RepoRules

**English** | [简体中文](README.md)

Turn the mechanical parts of a repository's rules into executable checks:
encoding and line endings, column width, forbidden patterns, header conventions,
version sync, changelog shape, required files, Markdown links and bilingual
pairs.

Python 3.9+, standard library only.

## Why

Rules in README/AGENTS.md rot: someone reads them, forgets one, and nothing
notices. RepoRules makes the **mechanically checkable** subset fail CI and
pre-commit. Judgement calls stay in the project's own `AGENTS.md`.

It does not compile, run tests, reformat with clang-format, or replace review.

## Quick start

```bash
python repo_rules.py check --config repo-rules.json
python repo_rules.py fix   --config repo-rules.json
python repo_rules.py init  --preset cpp-windows
python repo_rules.py sync  --root ../MyProject --hook
python repo_rules.py list-presets
```

Install as a command from a checkout:

```bash
pipx install .
repo-rules check --config repo-rules.json
```

You can also copy `repo_rules.py` into a project without installing anything.

## Add to an existing project

```bash
# run from the RepoRules checkout, or use `repo-rules init` when installed
python repo_rules.py init --root ../MyProject --preset cpp-windows
```

Then:

1. Edit the target `repo-rules.json` (especially `versions`,
   `required_files` and `markdown.bilingual_pairs`).
2. Run `python scripts/repo_rules.py check`.
3. Install the hook: `git config core.hooksPath .githooks`.
4. Keep the generated `.github/workflows/hygiene.yml` in CI.

`--no-tool` writes only the config and templates; `--force` overwrites existing
generated files.

### Update the vendored checker

`init` copies `repo_rules.py` into the target project, so that copy drifts as
RepoRules evolves. `sync` pushes the current version back:

```bash
python repo_rules.py sync --root ../MyProject            # refresh scripts/repo_rules.py
python repo_rules.py sync --root ../MyProject --hook     # also refresh .githooks/pre-commit
python repo_rules.py sync --root ../MyProject --check    # verify only; exit 1 when stale (CI-friendly)
```

`--dest` changes the copy path (default `scripts/repo_rules.py`); `--source`
picks a different checker as the source of truth.

## Built-in presets

| Preset | Purpose |
|---|---|
| `cpp-windows` | Windows/MSVC C++: C/C++ UTF-8 BOM+CRLF, docs CRLF, tooling LF, no `#pragma comment(lib)` |
| `cpp-library` | Header-only/cross-platform C++ style, similar rules |
| `python-tool` | Python tooling: all LF, version sync, changelog, README pair |

A preset is a starting point. Version sources and project paths are
project-specific; copy and edit.

## Rules

| Rule | Config key | What it checks |
|---|---|---|
| Encoding/EOL/BOM | `encoding` | Glob-matched policy, first match wins; `--fix` repairs this class |
| Column width | `width` | Tab-expanded width, default 140 |
| Forbidden pattern | `forbidden` | Regex + globs + rule id, e.g. no `#pragma comment(lib)` |
| Headers | `headers` | First significant line `#pragma once`; no namespace-scope `using namespace` |
| Version sync | `versions` | Captured groups across files must agree (CMake, `.rc`, header macros) |
| Changelog | `changelog` | Requires `## [Unreleased]`; every `## [x]` has `[x]: url` |
| Required files | `required_files` | LICENSE, README, CHANGELOG, etc. |
| Markdown | `markdown` | Relative links resolve; bilingual files link to each other |
| `.gitattributes` | `gitattributes` | Required regex patterns so the EOL policy is declared |

See [docs/configuration.md](docs/configuration.md) for the full schema and
examples, and [docs/adaptation.md](docs/adaptation.md) for migration steps.

## Scope

- No C++ AST; no semantic checks.
- Not a replacement for clang-format; width and forbidden patterns are the
  mechanical complements.
- It never rewrites Markdown or version numbers; `fix` only repairs
  encoding/BOM/line endings.
- No network, no execution of project code.
- Defaults are conservative; each project should state its own policy.

## Development

```bash
python -m unittest discover -s tests -v
python repo_rules.py check --config repo-rules.json
```

This repository checks itself with its own `repo-rules.json`. CI runs the
repository rules and the unit tests.

## License

MIT, see [LICENSE](LICENSE).
