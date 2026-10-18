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
is rooted at the repository root.

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

## `gitattributes`

```json
"gitattributes": {
  "path": ".gitattributes",
  "required_patterns": ["\\* text=auto", "\\*\\.py\\s+text eol=lf"]
}
```

Patterns are regular expressions searched in the file. This keeps the
line-ending policy declared in one place instead of only encoded in the checker.
