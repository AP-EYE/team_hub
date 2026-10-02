# AP-EYE team_hub 작업 규칙

Claude, Codex 등 이 레포에서 일하는 모든 AI와 사람이 따르는 규칙이다.
`CLAUDE.md`는 이 파일을 불러오기만 한다.

## 프로젝트

- 팀: AP-EYE (CCIT-2), API 인가 취약점(BOLA) 진단
- 교수: 조재현 교수, 최한림 교수. 두 분을 문서와 요약에서 멘토로 표기하지 않는다.
- 현재 방향 (2026-10-02 교수 피드백): 오픈소스 akto 리서치 후 기여 우선, 머지가 안 되면 fork해서 한국 특화와 BOLA 판정을 보강한다. 근거는 `review/2026-10-02-최한림-조재현.md`.
- 연구 범위: 읽기(조회) BOLA. 판정은 정상, 보류, BOLA 3단계.

## 시작 전

1. `git switch develop && git pull`
2. 작업 브랜치를 `develop`에서 만든다. 이름은 `타입/기능이름` (소문자, `-`).

## 산출물 위치

| 내용 | 폴더 |
|---|---|
| 코드 | `src/` |
| 연구 문서, 논문, 데이터셋, akto 리서치 | `docs/` |
| 교수·멘토 피드백 | `review/` |
| 회의록, 브리핑, 결정 기록 | `discussion/` |
| 아키텍처 설계, 다이어그램 | `arch/` |
| 개인 작업 메모 | `notes/<이름>/` |

`양유상/`은 기존 자료라 옮기거나 지우지 않는다.

## Git

- 세부 규칙은 `CONTRIBUTING.md`를 따른다.
- 커밋: `태그: 내용` (feat, fix, docs, style, refactor, chore)
- PR은 `develop`으로 올리고, 1명 이상 승인 후 머지한다. `main`, `develop`에 직접 push하지 않는다.

## 스킬

- 원본은 `.agents/skills/`다. 여기서만 고친다.
- `.claude/skills/`는 GitHub Action(`sync-skills`)이 PR마다 자동으로 복사한다. 직접 고치면 덮어써진다.
- Codex는 `.agents/skills/`, Claude Code는 `.claude/skills/`를 자동으로 읽는다.

## 노션

노션에 직접 쓰지 않는다. 레포의 md가 원본이고, 노션은 `notion-publish` 스킬로 발행한 사본이다.

## 문서 작성

- PDF, PPT, DOCX는 `to-markdown` 스킬로 md로 바꿔 원본 옆에 둔다.
- 논문을 근거로 쓸 때는 `paper-reading` 스킬을 따르고 읽기 수준(1차, 2차, 원문 미확인)을 적는다.
- 외부 사실에는 출처 URL을 붙인다. 모르는 값은 `TBD`로 두고 지어내지 않는다.
