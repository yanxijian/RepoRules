# CI 触发范围：只跑会变的东西

编译类流水线（`ci.yml`）只在可能改变构建产物的路径上启动；纯文档改动不跑完整编译。
仓库规范检查（`hygiene.yml`）相反，文档改动正是它要覆盖的对象，必须每次都跑。

## 两种写法

### A. 正向白名单（推荐）

只列出"能影响构建"的路径，其余一律不启动：

```yaml
on:
  push:
    branches: [main, master]
    paths: &build_inputs
      - "src/**"
      - "include/**"
      - "cmake/**"
      - "tests/**"
      - "CMakeLists.txt"
      - ".clang-format"
      - ".github/workflows/ci.yml"
  pull_request:
    paths: *build_inputs
  workflow_dispatch:
```

- 文档、`docs/`、`LICENSE`、`CHANGELOG.md` 自然被排除；改一句 README 不会拉起三个操作系统。
- YAML anchor（`&build_inputs` / `*build_inputs`）让 push 与 pull_request 共用一份列表，不会两边写歪。
- **代价**：漏列一条真实输入，该跑的不会跑，而且没有任何提示。新增目录、新增构建输入（例如换了依赖管理方式）时必须同步改这个列表——所以把它紧挨着 `on:` 写在最显眼的位置。
- 把 `.github/workflows/ci.yml` 自己也列进去：改流水线时跑一次，等于对流水线本身做冒烟。
- `workflow_dispatch` 不受 `paths` 约束，随时可以手动全量验证。

### B. 反向忽略

列出"不影响构建"的路径，其余全跑：

```yaml
on:
  push:
    branches: [main]
    paths-ignore:
      - "**/*.md"
      - "docs/**"
      - "LICENSE"
```

- 不会漏跑，但会多跑；每出现一类新的非代码文件就要补一条。
- **风险**：`**/*.md` 会把**测试夹具**一起忽略——有的解析器测试用 `.md` 当输入，改了夹具 CI 却不跑，测试"通过"但没验证。

## 怎么选

| 情况 | 选 |
| --- | --- |
| 构建输入可枚举、结构稳定（头文件库、单模块 CMake 工程） | A |
| 输入难以枚举，或宁可多跑也不能漏跑 | B |
| 依赖很多生成物、脚本层数深 | B 起步，等输入稳定后再收紧成 A |

同一个仓库内两种别混用；同一个工作区内的命名与注释保持一致，便于批量维护。

## 与 hygiene 的分工

| 流水线 | 触发范围 | 覆盖内容 |
| --- | --- | --- |
| `ci.yml` | 仅构建输入 | 编译、测试、clang-format |
| `hygiene.yml` | 全部改动 | 编码/行尾、Markdown 链接、双语互链、副本漂移 |

**不要把 `paths` 加到 `hygiene.yml`**：文档改动正是它要检查的对象，加了等于让规范检查对文档失效。
反过来，`ci.yml` 里不要再重复做规范检查——两边都做会让人分不清哪边失败该找谁。

## 注意

- **分支保护**：若把 `ci.yml` 的 check 设为 required，`paths` 过滤会让纯文档 PR 一直显示"等待该 check"，合并被卡。此时改用下面的 job 级门控。
- **定时任务不要加 `paths`**：夜间构建、soak、benchmark 的价值就在于"没改动也要跑一次"。
- 只想验证一次构建而不改代码时，用 `workflow_dispatch` 手动触发，不要为此提交一个空改动。

## job 级门控（需要保留 required check 时）

保留一个总是成功的轻量 job，用它给重活把关：

```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      code: ${{ steps.filter.outputs.code }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - id: filter
        shell: bash
        run: |
          base='${{ github.event.pull_request.base.sha || github.event.before }}'
          if git diff --name-only "$base" HEAD -- | grep -qvE '^(docs/|.*\.md$|LICENSE$)'; then
            echo "code=true"  >> "$GITHUB_OUTPUT"
          else
            echo "code=false" >> "$GITHUB_OUTPUT"
          fi

  build:
    needs: changes
    if: needs.changes.outputs.code == 'true'
    # ...构建步骤
```

- 判定方向必须是"**除文档外还有别的**"才跑（默认跑）：新增未知类型文件时倾向于跑，而不是静默跳过。
- 这段是草图：`base` 的取法随事件类型不同（push 用 `before`，PR 用 `base.sha`），落地时按仓库的触发方式调整。
- 代价是多一个 checkout 的 job；如果仓库没有 required check，直接用 A 更省。

## 落地时要改的地方

1. `ci.yml` 的 `on:` 段（本文件 A 或 B）。
2. 确认 `hygiene.yml` 不受影响（它应当完全不带 `paths`）。
3. 故意改一个 README 提交一次，确认编译流水线**没有**启动；再改一个 `src/` 文件，确认它**启动**了。
4. 把这个列表和构建结构写在同一处注意力范围内；新增顶层目录时回来看一眼。
