# RepoRules

[English](README.en.md) · **简体中文**

把仓库里“靠人记住”的机械规范变成可执行检查：编码与行尾、列宽、禁止模式、头文件约定、版本同步、CHANGELOG、必需文件、Markdown 链接和中英文互链。

Python 3.9+，只用标准库，无第三方依赖。

## 为什么

README/AGENTS.md 里的规则会腐烂：人读了、忘了，没人发现。RepoRules 把**能由程序判断**的部分固化成一个检查器，CI 和 pre-commit 都能运行；需要判断力的部分仍留在项目自己的 `AGENTS.md`。

它不负责编译、单元测试、clang-format 重排或代码审查。

## 快速开始

直接运行：

```bash
python repo_rules.py check --config repo-rules.json
python repo_rules.py fix   --config repo-rules.json
python repo_rules.py init  --preset cpp-windows
python repo_rules.py sync  --root ../MyProject --hook
python repo_rules.py list-presets
```

安装为命令（在源码目录）：

```bash
pipx install .
repo-rules check --config repo-rules.json
```

也可以只复制 `repo_rules.py` 到项目里，不安装任何东西。

## 引入到已有项目

```bash
# 在 RepoRules 源码目录执行；已安装时可直接用 `repo-rules init`
python repo_rules.py init --root ../MyProject --preset cpp-windows
```

然后：

1. 编辑目标项目的 `repo-rules.json`（尤其是 `versions`、`required_files` 和 `markdown.bilingual_pairs`）。
2. 运行 `python scripts/repo_rules.py check`。
3. 安装钩子：`git config core.hooksPath .githooks`。
4. 把生成的 `.github/workflows/hygiene.yml` 纳入 CI。

`--no-tool` 可以只生成配置和模板；`--force` 覆盖已生成文件。

### 升级已嵌入的检查器

`init` 会把 `repo_rules.py` 复制到目标项目，副本会随 RepoRules 升级而过期。用 `sync` 推回新版本：

```bash
python repo_rules.py sync --root ../MyProject            # 更新 scripts/repo_rules.py
python repo_rules.py sync --root ../MyProject --hook     # 同时更新 .githooks/pre-commit
python repo_rules.py sync --root ../MyProject --check    # 只检查：有落后副本时返回 1（适合 CI）
```

`--dest` 可改副本路径（默认 `scripts/repo_rules.py`）；`--source` 可指定其他版本作为来源。

## 内置 preset

| Preset | 用途 |
|---|---|
| `cpp-windows` | Windows/MSVC C++：C/C++ UTF-8 BOM+CRLF，文档 CRLF，工具 LF，禁止 `#pragma comment(lib)` |
| `cpp-library` | 头文件库/跨平台 C++ 风格，规则与 `cpp-windows` 类似 |
| `python-tool` | Python 工具：全部 LF，版本同步、CHANGELOG、README 中英文互链 |

preset 只是起点。版本号和路径因项目而异，复制后按项目修改。

## 规则

| 规则 | 配置键 | 说明 |
|---|---|---|
| 编码/行尾/BOM | `encoding` | 按 glob 匹配，首条命中生效；`--fix` 只修复这一类 |
| 列宽 | `width` | 按 tab width 展开后统计，默认 140 |
| 禁止模式 | `forbidden` | 正则 + glob + 规则 id，例如禁止 `#pragma comment(lib)` |
| 头文件 | `headers` | 首个有效行 `#pragma once`，禁止 namespace 级 `using namespace` |
| 版本同步 | `versions` | 多个文件的捕获组必须相等，例如 CMake、`.rc`、头文件宏 |
| CHANGELOG | `changelog` | 必需 `## [Unreleased]`，`## [x]` 必须有 `[x]: url` |
| 必需文件 | `required_files` | LICENSE、README、CHANGELOG 等 |
| Markdown | `markdown` | 相对链接可解析；双语文件互相链接 |
| `.gitattributes` | `gitattributes` | 必需的正则模式，确保行尾标准被声明 |

完整配置字段与示例见 [docs/configuration.md](docs/configuration.md)；迁移步骤见 [docs/adaptation.md](docs/adaptation.md)。

## 设计边界

- 不解析 C++ AST，不做语义检查。
- 不替代 clang-format；列宽和禁止模式是“可机械判定”的补充。
- 不改写 Markdown、不改写版本号；`fix` 只处理编码/BOM/行尾。
- 不访问网络，不执行项目代码。
- 规则默认值保守；项目应在配置里明确自己的策略。

## 开发

```bash
python -m unittest discover -s tests -v
python repo_rules.py check --config repo-rules.json
```

本仓库用自己的 `repo-rules.json` 自举检查。CI 运行仓库规则和单元测试。

## License

MIT，见 [LICENSE](LICENSE)。
