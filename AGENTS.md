# Agent instructions

Project-local rules for **RepoRules**. The workspace root `AGENTS.md` still
applies; this file narrows it for this repository.

## What this is

A zero-dependency Python tool that turns mechanical repository rules into
checks. The tool is intentionally a single file (`repo_rules.py`) so a project
can copy it without packaging.

- `repo_rules.py` - config model, checker, presets/init CLI.
- `presets/` - starting configurations.
- `templates/` - generated hook and CI workflow for target projects.
- `tests/` - unit tests for the engine.
- `repo-rules.json` - this repository's self-check configuration.

## Commands

```bash
python repo_rules.py check --config repo-rules.json
python repo_rules.py fix   --config repo-rules.json
python -m unittest discover -s tests -v
python repo_rules.py list-presets
```

Install the optional hook with `git config core.hooksPath .githooks`.

## Rules

- **Mechanical only.** Do not add build execution, network access, AST parsing or
  code formatting to the checker.
- `fix` may only repair `encoding` rules (BOM/EOL); never rewrite Markdown,
  version numbers or source text.
- Every new rule or config key needs a test and a `docs/configuration.md` entry.
- Presets are starting points, not project-specific configs. Keep them generic.
- Keep the tool single-file and Python 3.9 compatible; standard library only.
- Do not commit `build/`, `dist/`, `__pycache__/` or installed environments.
- All text files are UTF-8 + LF in this repository. `repo-rules.json` enforces
  the parts a program can check.

## Review priorities

Correctness of the check (no false negatives on the documented rule, no false
positives that make CI unusable), then config compatibility, then error
messages, then style.
