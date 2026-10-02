# Git Flow 전략 가이드

> 팀원들의 원활한 협업을 위한 Git Flow 전략

## 1. 팀원 합의 사항

- [x] **Git Client 도구 통일하기**
    - **VS Code** 내장 Git
- [x] **Merge 규칙 정하기**
    - **1명 이상의 Approve 후 Merge**
    - Why? 코드 충돌 방지 및 진행 상황 공유
- [x] **Merge 타이밍**
    - 기능 하나 완성될 때마다 수시로 **develop** 브랜치에 합치기

## 2. 브랜치 전략

### 구조도

- **main**
    - 완전히 작동하는 **최종 결과물**만 올라가는 곳
    - ex. 중간 발표 데모 버전, 최종 발표 버전
- **develop**
    - 각자 만든 기능이 하나로 합쳐지는 곳
    - 이곳의 코드는 항상 에러 없이 실행되어야 함
    - **Default Branch**
- **feature/...**
    - develop에서 복사해서 만드는 각자의 작업 공간
    - 기능 개발이 끝나면 develop으로 합쳐달라고 요청(PR)하고 삭제

### 브랜치 이름 규칙

> 타입/기능이름 (소문자와 -으로 통일)

| Type | 설명 | 예시 |
| --- | --- | --- |
| **feature** | 새로운 기능 개발 | feature/esp32-deauth |
| **fix** | 버그 수정 | fix/scapy-error |
| **docs** | 문서 작업 | docs/readme-update |
| **refactor** | 코드 정리/구조 변경 | refactor/api-cleanup |

## 3. 커밋 메시지 규칙

> [태그]: [작업 내용] 형식을 따릅니다.

| Tag | 의미 | 사용 예시 |
| --- | --- | --- |
| **feat** | 새로운 기능 추가 | feat: 로그인 페이지 UI 구현 |
| **fix** | 버그 수정 | fix: 와이파이 스캔 멈춤 오류 해결 |
| **docs** | 문서 수정 | docs: README 역할 분담표 업데이트 |
| **style** | 코드 포맷팅 (로직 변경 X) | style: 세미콜론 및 들여쓰기 정리 |
| **refactor** | 코드 리팩토링 | refactor: 중복 코드 함수화 |
| **chore** | 기타 설정, 자잘한 수정 | chore: 패키지 설치 및 설정 파일 변경 |

## 4. 작업 순서

1. **브랜치 생성**
    - develop 브랜치로 이동 후 `git pull`
    - 내 작업 브랜치 생성 (예: feature/login)
2. **코딩 및 커밋**
    - 작업 후 저장
    - `git add .` -> `git commit -m "feat: 로그인 버튼 추가"`
3. **업로드**
    - 내 브랜치를 깃허브 원격 저장소로 전송
    - `git push origin feature/login`
4. **검사 요청**
    - Github 페이지 접속 -> **[Compare & pull request]** 클릭
    - **Base: develop** <- **Compare: feature/login** 확인
    - 팀원들에게 PR 알리기
5. **병합**
    - 팀원이 코드 확인 후 **Merge** 버튼 클릭
    - 기능이 프로젝트에 반영
