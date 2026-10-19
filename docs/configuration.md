# Configuration reference

`repo-rules.json` is a JSON object with `"version": 1`. All paths are relative
to the repository root passed with `--root` (default: current directory).

Minimal example:

```json
{
  "version": 1,
  "encoding": [
    {"glob": "*.py", "bom": false, "eol": "lf"},
    {"glob": "*.md", "bom": false, "eol": "lf"}
  ],
  "required_files": ["LICENSE", "README.md"],
  "markdown": {"globs": ["*.md"], "check_links": true, "bilingual_pairs": []}
}
```

## `skip_dirs`, `skip_prefixes`, `skip_globs`

Directories are skipped before any rule runs.

```json
"skip_dirs": [".git", "build", "third_party"],
"skip_prefixes": ["build-", "cmake-build"],
"skip_globs": ["src/resources/resource.h"]
```

`skip_globs` uses shell-style matching against the repository-relative POSIX
path. A pattern without `/` matches a basename at any depth; a pattern with `/`
is rooted at the repository root. A skipped file is excluded from every rule,
including Markdown link checking — useful for documents that link into a
submodule which a CI checkout does not materialize.

## `encoding`

Each entry applies to the first matching glob:

```json
{
  "glob": "*.cpp",
  "bom": true,
  "eol": "crlf"
}
```

- `bom`: `true` requires/creates a UTF-8 BOM; `false` forbids/removes it.
- `eol`: `lf`, `crlf` or `any`.
- UTF-16 files and files with NUL bytes are reported instead of being decoded;
  add them to `skip_globs` (for example a generated `resource.h`).
- `check` reports violations; `fix` rewrites only files matched by this rule.

Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI, so any non-ASCII text
(Chinese comments, messages) is decoded as mojibake and may fail to parse. Keep
`"bom": true` for `*.ps1`; the built-in presets already do. Editors and agent
editing tools that write plain UTF-8 silently drop the BOM, so run `fix` after
touching such a file.

## `width`

```json
"width": {"globs": ["*.cpp", "*.h"], "limit": 140, "tab_width": 4}
```

Width is measured after expanding tabs and stripping trailing whitespace.

## `forbidden`

```json
{
  "id": "cmake-libs",
  "globs": ["*.cpp", "*.h"],
  "pattern": "#\\s*pragma\\s+comment\\s*\\(\\s*(lib|linker)",
  "message": "link Windows libraries through CMake target_link_libraries"
}
```

`pattern` is a Python regular expression searched line by line. `id` appears in
the report; keep it stable.

## `headers`

```json
"headers": {"globs": ["*.h", "*.hpp"], "first_line": "#pragma once", "forbid_namespace_using": true}
```

Comments are skipped when finding the first significant line. Namespace-scope
`using namespace` is reported when enabled.

## `versions`

Each group reads one regex per source. All captures from all sources must be
equal. Use non-capturing groups for parts that are not part of the version.

```json
"versions": [
  {
    "id": "product-version",
    "sources": [
      {"path": "CMakeLists.txt", "pattern": "VERSION\\s+(\\d+)\\.(\\d+)\\.(\\d+)"},
      {"path": "src/Version.rc", "pattern": "FILEVERSION\\s+(\\d+),(\\d+),(\\d+)(?:,\\d+)?"},
      {"path": "include/version.h", "pattern": "VERSION_MAJOR\\s+(\\d+)[\\s\\S]*?VERSION_MINOR\\s+(\\d+)[\\s\\S]*?VERSION_PATCH\\s+(\\d+)"}
    ]
  }
]
```

A missing file, a non-matching pattern, or no capture groups is a violation.

## `changelog`

```json
"changelog": {
  "path": "CHANGELOG.md",
  "require": "## [Unreleased]",
  "link_definitions": true
}
```

When `link_definitions` is true, every `## [x]` heading needs a
`[x]: <url>` definition. Set `"changelog": null` to disable.

## `required_files`

```json
"required_files": ["LICENSE", "README.md", "CHANGELOG.md"]
```

## `markdown`

```json
"markdown": {
  "globs": ["*.md"],
  "check_links": true,
  "bilingual_pairs": [["README.md", "README.en.md"]]
}
```

Relative links are resolved from the document's directory; external links,
fragments and root-absolute links are skipped. For each bilingual pair, each
file must contain the other file's basename (usually in the language switcher).

### `markdown.languages` (optional)

For repositories that ship one document in many languages. `bilingual_pairs`
only proves two files know about each other; this block also pins the **order**
and requires every variant to exist.

```json
"markdown": {
  "languages": {
    "default": "README.md",
    "variants": [
      "README.zh-CN.md",
      "README.ja.md",
      "README.ko.md"
    ],
    "switch_line": true
  }
}
```

| Key | Meaning |
|---|---|
| `default` | The file served when nobody asked for a language. Defaults to `README.md`. It must not also appear in `variants`. |
| `variants` | Ordered list of the other language files. Order is the contract: switch lines must follow it. |
| `switch_line` | Check the language switcher (default `true`). Set to `false` on a repo that only needs the completeness check. |
| `stale` | `off` (default), `warning` or `error`. On, every variant must carry `<!-- translated-from: <default> sha256:<12> -->`; a changed default reports `language-stale`. |

The switch line is the first significant line below the `H1`. It must:

1. start with the current language in bold (`**English**`), and
2. link to every other variant, in the configured order.

#### Keeping the variants honest (`stale`)

`switch_line` proves the four files know about each other; it says nothing about
whether they still say the same thing. Set `stale` to make that visible:

```json
"languages": {
  "default": "README.md",
  "variants": ["README.zh-CN.md", "README.ja.md", "README.ko.md"],
  "switch_line": true,
  "stale": "warning"
}
```

Each variant records the hash of the file it was translated from, at the top:

```markdown
<!-- translated-from: README.md sha256:5765763fdfd8 -->
```

When the default file changes, its hash changes and every variant reports
`language-stale` with both hashes. A missing marker is an error, because opting
into `stale` means every variant is tracked.

- `warning` (the recommended setting) prints the line and keeps the build green:
  translating is real work and must not block a merge, but it must not go
  unnoticed either.
- `error` fails the build. Use it only where translations are updated in the same
  change.
- The marker is a content hash, not a commit id, so a rebase does not invalidate
  every translation.

The old `markdown.translations` block is a different tool: it tracks *pairs of
documents* and can additionally check CJK line wrapping and cross-language links.
`markdown.languages.stale` tracks *one document in N languages*, which is the
README case.

HTML comments (`<!-- translated-from: ... -->`) before the title are ignored, so
a provenance marker does not shift the line. A section heading directly under the
title means there is no switch line and the check fails.

`markdown.languages` and `markdown.translations` are complementary: this block
checks presence, order and the switcher; `translations` checks the provenance
marker and whether a translation went stale.

### `markdown.translations.cover` (optional)

`pairs` is an explicit list, so a *new* document can appear without anyone
noticing that its translation is missing. `cover` closes that gap for a
directory pair where the documents are meant to be fully bilingual.

```json
"markdown": {
  "translations": {
    "pairs": [["docs/zh/build.md", "docs/en/build.md"]],
    "cover": [
      {"from": "docs/zh", "to": "docs/en", "ignore": ["product-plan.md"], "missing": "error"}
    ],
    "untracked": true
  }
}
```

| Key | Meaning |
|---|---|
| `from` | Source directory, relative to the repository root. Every `*.md` below it must exist at the same relative path under `to`. |
| `to` | Target (translation) directory. |
| `ignore` | Globs, relative to `from`, that are deliberately untranslated. A Chinese-only design note belongs here. |
| `missing` | `error` (default) or `warning`. |

One direction only, on purpose: a target file with no source counterpart is a
legitimately English-only document, not a gap. Check the direction you actually
translate.

`untracked: true` additionally reports a file that *looks like* a translation
(a target file that has a source counterpart, or a `*<suffix>` file) but is not
listed in `pairs`, so nothing ever checks it for staleness.

```text
docs/en/b.md: [translation-untracked] looks like a translation but is not listed
in markdown.translations.pairs, so it is never checked for staleness
```

### `markdown.translations` (optional)

Three checks for repositories that maintain a translated set of documents. Omit
the block and nothing changes.

```json
"markdown": {
  "translations": {
    "pairs": [["README.md", "README.zh-CN.md"]],
    "suffix": ".zh-CN.md",
    "marker": "translated-from:",
    "stale": "warning",
    "cjk_wrap": true,
    "keep_language": true
  }
}
```

| Key | Meaning |
|---|---|
| `pairs` | `[source, translation]` pairs. Both files must exist and the translation must carry the marker. |
| `suffix` | Suffix used to derive a sibling translation when checking links; default `.zh-CN.md`. |
| `marker` | Text that identifies the provenance comment, default `translated-from:`. |
| `stale` | `warning` (default) prints a `warn` line and exits 0; `error` fails; `off` skips the comparison. |
| `cjk_wrap` | Flag a line break between two CJK characters (Markdown renders it as a space). |
| `keep_language` | A translation must link to its translated siblings instead of the source-language files. |

The marker records the source revision the translation came from:

```markdown
<!-- translated-from: README.md sha256:1e739ff575ba -->
```

`sha256:` is the first 12 hex digits of the source file's SHA-256. Refreshing a
translation means updating this value by hand - the checker never edits
documents, it only reports drift.

## `comments`

Code comments are English. Other languages are allowed only for a quotation, a
data sample or a reference to a document heading, and those opt out per line.

```json
"comments": {
  "english": true,
  "globs": ["*.c", "*.h", "*.py", "*.sh", "*.ps1"],
  "allow_files": ["include/shell_ext/vendor/**"],
  "allow_marker": "cjk-ok"
}
```

| Key | Meaning |
|---|---|
| `english` | `true` (default) enables the check; `false` disables it. |
| `globs` | Which files to scan. Defaults to C/C++, Python, shell, PowerShell, JavaScript and batch files. |
| `allow_files` | Globs skipped entirely, for a file whose subject matter *is* another language. |
| `allow_marker` | A comment containing this token is skipped (default `cjk-ok`). Use it on the line that quotes something. |

The check looks for Han, Hiragana, Katakana, Hangul, CJK punctuation and fullwidth
forms inside comment text. It only reads shapes that are unambiguously comments:

- `//` and `/* */` for C/C++/JavaScript, tracked across lines;
- `#` for Python, shell and PowerShell;
- `REM` and `::` for batch files.

That last point matters: a `#define LABEL L"中文"` line is a preprocessor
directive, **not** a comment, and a `echo "中文"` line carries a string literal.
Neither is flagged, which is what keeps the rule usable on Windows-centric code.

```cpp
// 这是中文注释            -> flagged
/// Design doc "命中规则"  // cjk-ok   -> allowed
#define TITLE L"中文"                     -> allowed (string literal)
```

## `commit_message`

Commit messages are English. The check runs in the `commit-msg` hook, so a
non-English message is rejected before the commit exists.

```json
"commit_message": {
  "english": true,
  "allow_marker": "cjk-ok"
}
```

| Key | Meaning |
|---|---|
| `english` | `true` (default when the block is present) enables the check. Omit the block to disable it. |
| `allow_marker` | A message containing this token skips the check (default `cjk-ok`), for a message that quotes a Chinese title or a data sample. |

`repo-rules init` and `repo-rules sync --hook` install two hooks: `.githooks/pre-commit`
(runs `check --staged`) and `.githooks/commit-msg` (runs `check-msg`, which is what
rejects the message). Install them once per clone:

```bash
git config core.hooksPath .githooks
```

Run it by hand against an existing message file:

```bash
python scripts/repo_rules.py check-msg .git/COMMIT_EDITMSG --config repo-rules.json
```

The rule looks at the whole message, subject and body. It does not police the
*content*: a message that is English but useless still passes. That is a review
concern, not a mechanical one.

## `gitattributes`

```json
"gitattributes": {
  "path": ".gitattributes",
  "required_patterns": ["\\* text=auto", "\\*\\.py\\s+text eol=lf"]
}
```

Patterns are regular expressions searched in the file. This keeps the
line-ending policy declared in one place instead of only encoded in the checker.
