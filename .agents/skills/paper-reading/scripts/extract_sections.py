"""1차 읽기용: PDF에서 제목·Abstract·Introduction·결론 부분만 뽑는다.

사용: python extract_sections.py <pdf> [--max 6000]
제목은 첫 쪽 앞부분, 나머지는 제목줄(heading) 위치로 자른다.
heading을 못 찾으면 앞 2쪽과 References 직전 1.5쪽으로 대신한다.
"""
import re
import sys

from pypdf import PdfReader

INTRO = (r"(?:\n|^)\s*(?:1|I)\.?\s+Introduction\b|\n\s*(?:I\.\s*)?I\s?NTRODUCTION\b"
         r"|\n\s*Introduction\s*\n")
NEXT_AFTER_INTRO = r"\n\s*(?:2|II)\.?\s+[A-Z][^\n]{2,80}\n"
CONCL = (r"\n\s*(?:\d+|[IVX]+)?\.?\s*(?:Conclusions?|Concluding Remarks|Discussion|Limitations"
         r"|Threats to Validity|Future Work)[^\n]{0,60}\n")
REFS = r"\n\s*(?:References|REFERENCES|Bibliography)\s*\n"


def text_of(path):
    pages = [p.extract_text() or "" for p in PdfReader(path).pages]
    return pages, "\n".join(pages)


def cut(t, start_pat, end_pat, limit):
    m = re.search(start_pat, t)
    if not m:
        return None
    rest = t[m.start():]
    e = re.search(end_pat, rest[50:])
    seg = rest[: e.start() + 50] if e else rest
    return seg[:limit]


def main():
    path = sys.argv[1]
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 6000
    pages, t = text_of(path)
    refs = re.search(REFS, t)
    body = t[: refs.start()] if refs else t

    print("=== TITLE + ABSTRACT ===")
    intro_m = re.search(INTRO, body)
    print(body[: intro_m.start() if intro_m else 3000][:limit])

    print("\n=== INTRODUCTION ===")
    intro = cut(body, INTRO, NEXT_AFTER_INTRO, limit)
    print(intro if intro else "\n".join(pages[:2])[:limit])

    print("\n=== CONCLUSION / DISCUSSION / LIMITATIONS ===")
    ms = list(re.finditer(CONCL, body))
    if ms:
        # 마지막 결론류 heading 중 가장 앞의 것부터 References 직전까지
        first = ms[0] if len(ms) <= 2 else ms[-2]
        print(body[first.start():][: limit * 2])
    else:
        print(body[-int(limit * 1.5):])


if __name__ == "__main__":
    main()
