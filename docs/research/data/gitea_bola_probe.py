"""Gitea 로컬 인스턴스에서 공개/비공개/공유 테스트 객체를 만들고
계정별 조회 결과를 단순 규칙("타인이 200 받으면 위반")과 정답(지정한 공개 상태)으로 비교한다.

전제: docker 컨테이너 gitea-bola 가 localhost:3300 에서 실행 중이고
관리자 rootadm / Rootpass123! 가 CLI로 생성돼 있다.
"""
import base64
import json
import time
import urllib.error
import urllib.request

BASE = "http://localhost:3300/api/v1"
ADMIN = ("rootadm", "Rootpass123!")
PW = "Testpass123!"
USERS = {"A": "alice", "B": "bob", "C": "carol"}  # A 주인, B 권한 없음, C 공유받음


def call(method, path, auth=None, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    if token:
        req.add_header("Authorization", "token " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")[:120]


def wait():
    for _ in range(60):
        try:
            if call("GET", "/version")[0] == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit("gitea not ready")


def setup():
    tokens = {}
    for role, name in USERS.items():
        call("POST", "/admin/users", auth=ADMIN, body={
            "username": name, "email": f"{name}@test.local", "password": PW,
            "must_change_password": False})
        st, tok = call("POST", f"/users/{name}/tokens", auth=(name, PW), body={
            "name": f"probe-{int(time.time())}",
            "scopes": ["write:repository", "write:issue", "read:user"]})
        assert st == 201, (name, st, tok)
        tokens[role] = tok["sha1"]
    # ponytail: 준비 단계는 alice 기본 인증으로 한다. 토큰 scope 차이로 생성이 404 나는 것을 피하고, 조회만 토큰으로 한다.
    a = ("alice", PW)
    for repo, private in (("pub", False), ("priv", True), ("shared", True)):
        st, _ = call("POST", "/user/repos", auth=a, body={"name": repo, "private": private, "auto_init": True})
        assert st in (201, 409), (repo, st)
        if call("GET", f"/repos/alice/{repo}/issues/1", auth=a)[0] != 200:
            st, _ = call("POST", f"/repos/alice/{repo}/issues", auth=a, body={"title": f"{repo} issue"})
            assert st == 201, (repo, "issue", st)
    st, _ = call("PUT", "/repos/alice/shared/collaborators/carol", auth=a, body={"permission": "read"})
    assert st in (204, 201), st
    return tokens


# 정답: 객체별로 누가 읽어도 되는가 (테스트 객체에 미리 지정한 상태)
ALLOWED = {
    "pub": {"A", "B", "C", "anon"},
    "priv": {"A"},
    "shared": {"A", "C"},
}
PATHS = {"repo": "/repos/alice/{r}", "issue": "/repos/alice/{r}/issues/1"}


def main():
    wait()
    tokens = setup()
    rows = []
    for repo, allowed in ALLOWED.items():
        for kind, tmpl in PATHS.items():
            for who in ("B", "C", "anon"):
                st, body = call("GET", tmpl.format(r=repo), token=tokens.get(who))
                got = st == 200
                private_field = None
                if kind == "repo" and isinstance(body, dict):
                    private_field = body.get("private")
                naive = "위반" if got else "정상"           # 단순 규칙: 타인이 200이면 위반
                truth_forbidden = who not in allowed
                if got and truth_forbidden:
                    truth = "위반"
                else:
                    truth = "정상"
                rows.append((repo, kind, who, st, private_field, naive, truth))
    print("repo    kind   who   status private  naive  truth  naive_correct")
    fp = 0
    for r in rows:
        ok = r[5] == r[6]
        fp += (r[5] == "위반" and r[6] == "정상")
        print(f"{r[0]:<7} {r[1]:<6} {r[2]:<5} {r[3]:<6} {str(r[4]):<8} {r[5]:<5}  {r[6]:<5}  {ok}")
    print(f"naive false positives: {fp}/{len(rows)}")


if __name__ == "__main__":
    main()
