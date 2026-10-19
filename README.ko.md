# RepoRules

**한국어** · [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

<!-- translated-from: README.md sha256:b4c8c23d52bb -->

저장소 규칙 가운데 "사람 기억에 의존하는" 기계적인 부분을 실행 가능한 검사로 바꿉니다. 인코딩과 줄바꿈, 열 너비, 금지 패턴, 헤더 규약, 버전 동기화, CHANGELOG 형태, 필수 파일, Markdown 링크, 다국어 문서 세트가 대상입니다.

Python 3.9 이상, 표준 라이브러리만 사용하며 서드파티 의존성은 없습니다.

## 왜

README/AGENTS.md에 적은 규칙은 썩습니다. 누군가 읽고, 하나를 잊고, 아무도 알아채지 못합니다. RepoRules는 **프로그램이 판정할 수 있는 부분**을 CI와 pre-commit에서 실패하게 만듭니다. 판단이 필요한 부분은 프로젝트의 `AGENTS.md`에 남깁니다.

컴파일, 테스트 실행, clang-format 재정렬, 리뷰 대체는 하지 않습니다.

## 빠른 시작

바로 실행:

```bash
python repo_rules.py check --config repo-rules.json
python repo_rules.py fix   --config repo-rules.json
python repo_rules.py init  --preset cpp-windows
python repo_rules.py sync  --root ../MyProject --hook
python repo_rules.py list-presets
```

체크아웃에서 명령으로 설치:

```bash
pipx install .
repo-rules check --config repo-rules.json
```

`repo_rules.py` 파일만 프로젝트에 복사해도 됩니다. 아무것도 설치하지 않아도 됩니다.

## 기존 프로젝트에 도입

```bash
# RepoRules 체크아웃에서 실행(설치했다면 `repo-rules init`도 가능)
python repo_rules.py init --root ../MyProject --preset cpp-windows
```

그다음:

1. 대상 `repo-rules.json`을 고칩니다(특히 `versions`, `required_files`, `markdown.languages`, `markdown.translations`).
2. `python scripts/repo_rules.py check`를 실행합니다.
3. 훅을 설치합니다: `git config core.hooksPath .githooks`.
4. 생성된 `.github/workflows/hygiene.yml`을 CI에 둡니다.

`--no-tool`은 설정과 템플릿만 쓰고, `--force`는 이미 생성된 파일을 덮어씁니다.

### 내장 검사기 업데이트

`init`은 `repo_rules.py`를 대상 프로젝트로 복사하므로, RepoRules가 발전하면 그 사본은 낡습니다. `sync`로 현재 버전을 되돌려 넣습니다:

```bash
python repo_rules.py sync --root ../MyProject            # scripts/repo_rules.py 갱신
python repo_rules.py sync --root ../MyProject --hook     # .githooks/pre-commit도 갱신
python repo_rules.py sync --root ../MyProject --check    # 검사만. 낡았으면 종료 코드 1(CI용)
```

`--dest`로 사본 경로(기본 `scripts/repo_rules.py`), `--source`로 다른 검사기를 기준으로 지정할 수 있습니다.

## 내장 preset

| Preset | 용도 |
|---|---|
| `cpp-windows` | Windows/MSVC C++: C/C++는 UTF-8 BOM+CRLF, 문서는 CRLF, 도구는 LF, `#pragma comment(lib)` 금지 |
| `cpp-library` | 헤더 온리/크로스 플랫폼 C++ 스타일. 규칙은 `cpp-windows`와 비슷함 |
| `python-tool` | Python 도구: 전부 LF, 버전 동기화, CHANGELOG, README 대역 |

preset은 출발점일 뿐입니다. 버전 출처와 경로는 프로젝트마다 다르니 복사한 뒤 고쳐 쓰세요.

## 규칙

| 규칙 | 설정 키 | 검사 내용 |
|---|---|---|
| 인코딩/줄바꿈/BOM | `encoding` | glob별 정책, 첫 번째 일치가 적용. `--fix`는 이 분류만 고침 |
| 열 너비 | `width` | 탭을 펼쳐서 세며 기본값 140 |
| 금지 패턴 | `forbidden` | 정규식 + glob + 규칙 id. 예: `#pragma comment(lib)` 금지 |
| 헤더 | `headers` | 첫 유효 줄이 `#pragma once`. 네임스페이스 스코프의 `using namespace` 금지 |
| 버전 동기화 | `versions` | 여러 파일의 캡처 그룹이 같아야 함(CMake, `.rc`, 헤더 매크로) |
| CHANGELOG | `changelog` | `## [Unreleased]` 필수. 각 `## [x]`에는 `[x]: url` 필요 |
| 필수 파일 | `required_files` | LICENSE, README, CHANGELOG 등 |
| Markdown | `markdown` | 상대 링크가 풀려야 함. 다국어 세트가 빠짐없이 있고 순서가 맞아야 함 |
| `.gitattributes` | `gitattributes` | 줄바꿈 정책이 선언됐는지 확인하는 필수 정규식 |

`markdown.languages`는 "문서 하나에 N개 언어판이 있는" 경우를 검사합니다. 모든 판이 존재하고, 제목 바로 아래 전환 줄이 현재 언어를 굵게 맨 앞에 두며, 설정한 순서대로 나머지 판에 링크해야 합니다. 출처 표시가 있는 번역 검사(`translated-from`, 번역 노후화, CJK 줄바꿈)는 `markdown.translations`를 씁니다.

설정 항목 전체와 예시는 [docs/configuration.md](docs/configuration.md), 마이그레이션 절차는 [docs/adaptation.md](docs/adaptation.md), CI 트리거 범위(문서만 바뀔 때 빌드를 돌리지 않기)는 [docs/ci-scheduling.md](docs/ci-scheduling.md)를 보세요.

## 설계 경계

- C++ AST를 분석하지 않고 의미 검사도 하지 않습니다.
- clang-format을 대체하지 않습니다. 열 너비와 금지 패턴은 그 기계적인 보완입니다.
- Markdown이나 버전 번호를 고쳐 쓰지 않습니다. `fix`가 다루는 것은 인코딩/BOM/줄바꿈뿐입니다.
- 네트워크에 접근하지 않고 프로젝트 코드도 실행하지 않습니다.
- 기본값은 보수적입니다. 프로젝트가 자기 정책을 설정에 분명히 적어야 합니다.

## 개발

```bash
python -m unittest discover -s tests -v
python repo_rules.py check --config repo-rules.json
```

이 저장소는 자체 `repo-rules.json`으로 스스로를 검사합니다. CI는 저장소 규칙과 단위 테스트를 실행합니다.

## 라이선스

MIT. [LICENSE](LICENSE)를 보세요.
