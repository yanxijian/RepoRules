# RepoRules

**日本語** · [English](README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)

<!-- translated-from: README.md sha256:b4c8c23d52bb -->

リポジトリの規約のうち「人の記憶に頼っている」機械的な部分を、実行できるチェックに変えます。文字コードと改行、桁幅、禁止パターン、ヘッダーの取り決め、バージョンの同期、CHANGELOG の形、必須ファイル、Markdown のリンク、多言語のドキュメントセットが対象です。

Python 3.9 以降。標準ライブラリのみで、サードパーティ依存はありません。

## なぜ

README や AGENTS.md に書いた規約は腐ります。誰かが読み、一つ忘れ、それに気づく人がいない。RepoRules は**プログラムで判定できる部分**を CI と pre-commit で落とします。判断が必要な部分は、プロジェクト自身の `AGENTS.md` に残します。

コンパイル、テスト実行、clang-format による整形、レビューの代替はしません。

## クイックスタート

そのまま実行する場合：

```bash
python repo_rules.py check --config repo-rules.json
python repo_rules.py fix   --config repo-rules.json
python repo_rules.py init  --preset cpp-windows
python repo_rules.py sync  --root ../MyProject --hook
python repo_rules.py list-presets
```

チェックアウトからコマンドとして入れる場合：

```bash
pipx install .
repo-rules check --config repo-rules.json
```

`repo_rules.py` をプロジェクトにコピーするだけでも使えます。何もインストールする必要はありません。

## 既存プロジェクトへの導入

```bash
# RepoRules のチェックアウトで実行（導入済みなら `repo-rules init` でも可）
python repo_rules.py init --root ../MyProject --preset cpp-windows
```

そのあと：

1. 対象の `repo-rules.json` を編集する（特に `versions`、`required_files`、`markdown.languages`、`markdown.translations`）。
2. `python scripts/repo_rules.py check` を実行する。
3. フックを入れる：`git config core.hooksPath .githooks`。
4. 生成された `.github/workflows/hygiene.yml` を CI に残す。

`--no-tool` は設定とテンプレートだけを書き、`--force` は生成済みファイルを上書きします。

### 同梱チェッカーの更新

`init` は `repo_rules.py` を対象プロジェクトにコピーするため、RepoRules が進むほどそのコピーは古くなります。`sync` で現在の版を押し戻します：

```bash
python repo_rules.py sync --root ../MyProject            # scripts/repo_rules.py を更新
python repo_rules.py sync --root ../MyProject --hook     # .githooks/pre-commit も更新
python repo_rules.py sync --root ../MyProject --check    # 検査のみ。古いと終了コード 1（CI 向け）
```

`--dest` でコピー先（既定は `scripts/repo_rules.py`）、`--source` で別のチェッカーを正とする指定ができます。

## 組み込み preset

| Preset | 用途 |
|---|---|
| `cpp-windows` | Windows/MSVC の C++：C/C++ は UTF-8 BOM+CRLF、ドキュメントは CRLF、ツール類は LF、`#pragma comment(lib)` を禁止 |
| `cpp-library` | ヘッダーオンリー／クロスプラットフォーム向けの C++ 流儀。規則は `cpp-windows` とほぼ同じ |
| `python-tool` | Python ツール：すべて LF、バージョン同期、CHANGELOG、README の対訳 |

preset は出発点です。バージョンの出どころやパスはプロジェクトごとに違うので、コピーして編集してください。

## 規則

| 規則 | 設定キー | 検査内容 |
|---|---|---|
| 文字コード／改行／BOM | `encoding` | glob ごとの方針。最初に一致したものが有効。`--fix` はこの分類だけを直す |
| 桁幅 | `width` | タブを展開して数える。既定は 140 |
| 禁止パターン | `forbidden` | 正規表現＋glob＋規則 id。例：`#pragma comment(lib)` の禁止 |
| ヘッダー | `headers` | 最初の有効行が `#pragma once`。名前空間スコープの `using namespace` を禁止 |
| バージョン同期 | `versions` | 複数ファイルの捕捉グループが一致すること（CMake、`.rc`、ヘッダーのマクロ） |
| CHANGELOG | `changelog` | `## [Unreleased]` が必須。各 `## [x]` には `[x]: url` が必要 |
| 必須ファイル | `required_files` | LICENSE、README、CHANGELOG など |
| Markdown | `markdown` | 相対リンクが解決できること。多言語セットが揃い、順序が正しいこと |
| `.gitattributes` | `gitattributes` | 改行方針が宣言されていることを確かめる必須の正規表現 |

`markdown.languages` は「1 つの文書セットに N 言語の版がある」場合の規則です。すべての版が存在し、タイトル直下の切り替え行が現在の言語を太字で先頭に置き、設定した順序で他の版へリンクしていることを検査します。出典マーカー付きの翻訳検査（`translated-from`、訳の陳腐化、CJK の折り返し）は `markdown.translations` を使います。

設定項目の全体と例は [docs/configuration.md](docs/configuration.md)、移行手順は [docs/adaptation.md](docs/adaptation.md)、CI の起動範囲（ドキュメントだけの変更でビルドを走らせない）は [docs/ci-scheduling.md](docs/ci-scheduling.md) を参照してください。

## 設計上の線引き

- C++ の AST は解析しません。意味的な検査もしません。
- clang-format の代わりではありません。桁幅と禁止パターンは、その機械的な補完です。
- Markdown もバージョン番号も書き換えません。`fix` が扱うのは文字コード／BOM／改行だけです。
- ネットワークにアクセスせず、プロジェクトのコードも実行しません。
- 既定値は保守的です。プロジェクトが自分の方針を設定に明記してください。

## 開発

```bash
python -m unittest discover -s tests -v
python repo_rules.py check --config repo-rules.json
```

このリポジトリは自分の `repo-rules.json` で自己検査しています。CI ではリポジトリ規則と単体テストを実行します。

## ライセンス

MIT。[LICENSE](LICENSE) を参照してください。
