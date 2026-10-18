# 引入与迁移

RepoRules 面向“已有项目逐步接入”，不要求一次把规则开满。

## 1. 选择 preset

- Windows/MSVC C++：`cpp-windows`
- 头文件库/跨平台 C++：`cpp-library`
- Python 工具：`python-tool`

```bash
python repo_rules.py init --root ../MyProject --preset cpp-windows
```

它会在目标项目写入：

```text
repo-rules.json
scripts/repo_rules.py
.githooks/pre-commit
.github/workflows/hygiene.yml
```

已有的文件默认保留；确实要覆盖时加 `--force`。只想要配置和模板时加
`--no-tool`。

## 2. 先只检查，不修复

```bash
cd ../MyProject
python scripts/repo_rules.py check
```

根据输出逐条调整 `repo-rules.json`：

- 第三方、生成目录加入 `skip_dirs` / `skip_globs`
- UTF-16 资源文件加入 `skip_globs`
- 只把当前仓库真正遵守的规则打开
- `required_files` 先填已有文件

确认规则集合合理后再运行：

```bash
python scripts/repo_rules.py fix
git diff --stat
```

`fix` 只处理 `encoding` 规则里的 BOM/行尾，不改内容、不重排代码。

## 3. 声明 `.gitattributes`

C/C++ 使用 BOM+CRLF 的项目，建议用 `-text -eol` 保存原始字节，避免 Git
在提交/检出自作主张转换：

```gitattributes
* text=auto
*.cpp -text -eol
*.h   -text -eol
*.md  -text -eol
*.py  text eol=lf
```

文档使用 CRLF 时同样建议 `-text -eol`；纯 LF 项目用 `text eol=lf`。
把关键模式写入 `gitattributes.required_patterns`，让检查器同时验证声明。

## 4. 版本同步

C++ DLL/项目的常见三处版本：

```json
"versions": [
  {
    "id": "dll-version",
    "sources": [
      {
        "path": "CMakeLists.txt",
        "pattern": "project\\s*\\([^)]*?VERSION\\s+(\\d+)\\.(\\d+)\\.(\\d+)"
      },
      {
        "path": "src/resources/Version.rc",
        "pattern": "FILEVERSION\\s+(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)(?:,\\d+)?"
      },
      {
        "path": "include/shell_ext/common.h",
        "pattern": "SHELLEXT_VERSION_MAJOR\\s+(\\d+)[\\s\\S]*?SHELLEXT_VERSION_MINOR\\s+(\\d+)[\\s\\S]*?SHELLEXT_VERSION_PATCH\\s+(\\d+)"
      }
    ]
  }
]
```

用非捕获组处理 `FILEVERSION` 的第四个 build 字段，避免 3 组 vs 4 组不匹配。
这些路径和宏名是项目自己的，preset 不会猜。

## 5. 钩子与 CI

```bash
git config core.hooksPath .githooks
```

pre-commit 使用 `check --staged`，只检查暂存文件；CI 模板使用全量检查。
两者都调用目标项目里的 `scripts/repo_rules.py`，不依赖全局安装。

CI 模板是独立的 `hygiene.yml`，与构建 CI 分开：文档/配置改动也要跑仓库规则。
反向的规则同样成立——构建 CI 只应在构建输入变化时启动，纯文档改动不该拉起完整编译，
见 [ci-scheduling.md](ci-scheduling.md)。

## 6. 逐步收紧

建议顺序：

1. 行尾/BOM（先 `fix`，再纳入检查）
2. 禁止模式（例如 `#pragma comment(lib)`）
3. 头文件约定、列宽
4. 版本同步、CHANGELOG
5. Markdown 链接、双语互链
6. `required_files`、`.gitattributes` 模式

每加一条规则，先跑 `check` 看现有违规量；不要一次性打开导致无法合并的规则。
