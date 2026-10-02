# AP-EYE team_hub

AP-EYE(CCIT-2) 팀의 코드, 연구 문서, 피드백, 회의 기록을 모으는 단일 저장소다.
노션 대신 여기가 원본이다. 작업 규칙은 [`AGENTS.md`](AGENTS.md), Git 규칙은 [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 폴더

| 폴더 | 내용 |
|---|---|
| [`src/`](src/) | 팀 코드 |
| [`docs/`](docs/) | 연구 문서, 논문, 데이터셋, akto 리서치 |
| [`review/`](review/) | 교수·멘토 피드백 |
| [`discussion/`](discussion/) | 회의록, 브리핑, 결정 기록 |
| [`arch/`](arch/) | 아키텍처 설계와 다이어그램 |
| `notes/<이름>/` | 개인 작업 메모 |
| [`.agents/skills/`](.agents/skills/) | 팀 공용 AI 스킬 (원본) |
| [`양유상/`](양유상/) | 기존 자료 (아래 색인) |

## 기존 자료 색인

- [`양유상/데모코드/`](양유상/데모코드/): API 보안 게이트웨이 킥오프 데모 코드와 평가 증거
- [`양유상/데모코드/docs/architecture.md`](양유상/데모코드/docs/architecture.md): 킥오프 데모 아키텍처
- [`양유상/조사/`](양유상/조사/): API 보안 게이트웨이 조사 (2026-09-21)
- [`양유상/시연영상/`](양유상/시연영상/): 데모 촬영 안내와 근거 문서
- [`양유상/데모-해석-상세.md`](양유상/데모-해석-상세.md): 데모 해석 문서

## 처음 세팅

1. `git clone https://github.com/AP-EYE/team_hub && cd team_hub && git switch develop`
2. 이 폴더에서 Claude Code나 Codex를 실행하면 팀 스킬과 `AGENTS.md`가 자동으로 적용된다.
3. 작업 전에는 항상 `git pull`.

## 외부 링크

- WBS: https://docs.google.com/spreadsheets/d/1BEng0hf4ecWgnHRY2qnwIZOsEwE1eXWsl9n3laP2AFA/edit?usp=sharing
