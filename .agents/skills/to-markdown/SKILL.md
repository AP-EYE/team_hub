---
name: to-markdown
description: PDF, PPT(X), DOCX, XLSX, HTML 파일을 md로 바꿔 레포에 올리는 스킬. 다음 상황이면 사용 - "이거 md로 바꿔줘", "PDF 정리해서 올려줘", "발표자료 레포에 넣어줘", 논문 PDF나 PPT를 docs/에 추가할 때. 원본 파일은 그대로 두고 같은 폴더에 같은 이름의 .md를 만든다.
---

# 파일을 md로 바꾸기

## 실행

```bash
uvx --from 'markitdown[all]' markitdown <원본파일> -o <원본과 같은 이름>.md
```

`uvx`가 없으면 `pip install 'markitdown[all]'` 후 `markitdown <원본파일> -o <출력>.md`.

## 위치

| 원본 | 둘 곳 |
|---|---|
| 논문 PDF | `docs/papers/` (원본 이름 `<약칭>_<식별자>.pdf`) |
| 발표·브리핑 PPT | `discussion/briefing/` |
| 기획·제안서 | `docs/plan/` |
| 그 밖의 자료 | `docs/` 아래 주제 폴더 |

원본과 md를 같은 폴더에 둔다. 예: `docs/papers/AuthProbe_2607.20574.pdf`와 `docs/papers/AuthProbe_2607.20574.md`.

## 변환 후 확인

1. md 맨 위에 `> 원본: <파일명>, 변환: markitdown, YYYY-MM-DD` 한 줄을 넣는다.
2. 표와 수식이 깨졌는지 원본과 한 번 대조한다. 깨진 곳은 `<!-- 변환 깨짐: 원본 p.N 참조 -->`로 표시하고 지어내서 채우지 않는다.
3. 스캔본이라 텍스트가 비면 그 사실을 PR 설명에 적는다.
4. 논문은 변환 후 `paper-reading` 스킬로 읽는다.
