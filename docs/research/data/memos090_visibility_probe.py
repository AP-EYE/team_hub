"""Memos 0.9.0(로컬 docker memos-090, localhost:5230)에서 메모별 공개 범위가 되는지,
그리고 다른 계정·비로그인으로 GET /api/memo/{id} 했을 때 결과를 기록한다.
0.9.0 API 경로는 소스·문서로 확정하지 않았으므로 응답을 그대로 출력해 확인한다.
"""
import http.cookiejar
import json
import urllib.error
import urllib.request

BASE = "http://localhost:5230"


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(op, method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with op.open(req) as r:
            raw = r.read().decode()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def data(raw):
    try:
        j = json.loads(raw)
        return j.get("data", j)
    except Exception:
        return raw


def main():
    alice, bob, anon = client(), client(), client()
    print("signup alice", call(alice, "POST", "/api/auth/signup",
                               {"username": "alice", "password": "alicepass", "role": "HOST"})[0])
    print("signin alice", call(alice, "POST", "/api/auth/signin",
                               {"username": "alice", "password": "alicepass"})[0])
    st, raw = call(alice, "POST", "/api/user", {"username": "bobby", "password": "bobbypass", "role": "USER"})
    print("create bob", st, raw[:120])
    print("signin bob", call(bob, "POST", "/api/auth/signin", {"username": "bobby", "password": "bobbypass"})[0])

    ids = {}
    for vis in ("PUBLIC", "PROTECTED", "PRIVATE"):
        st, raw = call(alice, "POST", "/api/memo", {"content": f"{vis} memo", "visibility": vis})
        d = data(raw)
        ids[vis] = d.get("id") if isinstance(d, dict) else None
        print("create", vis, st, "id", ids[vis], "visibility", d.get("visibility") if isinstance(d, dict) else raw[:120])

    # 정답: 메모를 만들 때 지정한 공개 범위로 누가 읽어도 되는지 정한다
    allowed = {"PUBLIC": {"bobby", "anon"}, "PROTECTED": {"bobby"}, "PRIVATE": set()}
    print("\nmemo       who    status  visibility  naive  truth  naive_correct")
    rows = []
    for vis, mid in ids.items():
        for who, op in (("bobby", bob), ("anon", anon)):
            st, raw = call(op, "GET", f"/api/memo/{mid}")
            d = data(raw)
            got = st == 200
            naive = "위반" if got else "정상"  # 단순 규칙: 주인이 아닌데 200이면 위반
            truth = "위반" if got and who not in allowed[vis] else "정상"
            rows.append((naive, truth))
            shown = d.get("visibility") if isinstance(d, dict) else "-"
            print(f"{vis:<10} {who:<6} {st:<7} {str(shown):<11} {naive:<5}  {truth:<5}  {naive == truth}")
    fp = sum(1 for n, t in rows if n == "위반" and t == "정상")
    print(f"naive false positives: {fp}/{len(rows)}")


if __name__ == "__main__":
    main()
