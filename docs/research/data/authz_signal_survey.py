"""APIs.guru 공개 OpenAPI 명세에서 GET 2xx 응답 스키마가 권한 상태 단서 필드를 노출하는 비율을 센다.

범주:
  VIS   공개·비공개 상태 (visibility, is_public, private ...)
  SHARE 공유·ACL (shared_with, acl, permissions, collaborators ...)
  OWNER 소유자 신원 (owner, owner_id, created_by ...)
출력: research/authz_signal_survey.json (명세별 결과), 표준출력 요약
"""
import json, re, sys, urllib.request, concurrent.futures as cf
from urllib.parse import urlparse

UA = {"User-Agent": "Mozilla/5.0 (academic survey script)"}
PATTERNS = {
    "VIS": re.compile(r"^(is_?)?(public|private|hidden|secret)$|^visibility$|^privacy(_?(level|setting|status))?$|^(access|audience)_?(type|scope)?$", re.I),
    "SHARE": re.compile(r"^(shared_?with|sharing|shares|share_?settings|collaborators|acl|acls|access_?control(_?list)?|permissions?|access_?level|allowed_?users)$", re.I),
    "OWNER": re.compile(r"^(owner|owner_?id|owner_?user(_?id)?|created_?by|creator(_?id)?|author(_?id)?|user_?id)$", re.I),
}
BIG = ("azure.com", "googleapis.com", "amazonaws.com", "microsoft.com")


def get_json(url, timeout=30):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read())


def resolve(spec, ref):
    if not ref.startswith("#/"):
        return None
    node = spec
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def collect_props(spec, schema, seen, out, depth=0):
    if not isinstance(schema, dict) or depth > 8:
        return
    ref = schema.get("$ref")
    if ref:
        if ref in seen:
            return
        seen.add(ref)
        collect_props(spec, resolve(spec, ref), seen, out, depth + 1)
        return
    for key in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(key, []) or []:
            collect_props(spec, sub, seen, out, depth + 1)
    if "items" in schema:
        collect_props(spec, schema["items"], seen, out, depth + 1)
    props = schema.get("properties") or {}
    if isinstance(props, dict):
        for name, sub in props.items():
            out.add(name)
            collect_props(spec, sub, seen, out, depth + 1)
    if isinstance(schema.get("additionalProperties"), dict):
        collect_props(spec, schema["additionalProperties"], seen, out, depth + 1)


def get_response_props(spec):
    names, n_get = set(), 0
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        op = item.get("get")
        if not isinstance(op, dict):
            continue
        n_get += 1
        for code, resp in (op.get("responses") or {}).items():
            if not str(code).startswith("2"):
                continue
            if isinstance(resp, dict) and "$ref" in resp:
                resp = resolve(spec, resp["$ref"]) or {}
            if not isinstance(resp, dict):
                continue
            schemas = []
            if "schema" in resp:  # swagger 2
                schemas.append(resp["schema"])
            for media in (resp.get("content") or {}).values():  # openapi 3
                if isinstance(media, dict) and "schema" in media:
                    schemas.append(media["schema"])
            for s in schemas:
                collect_props(spec, s, set(), names)
    return names, n_get


def analyze(item):
    api_id, url = item
    try:
        spec = get_json(url)
        names, n_get = get_response_props(spec)
        hits = {c: sorted(n for n in names if p.match(n)) for c, p in PATTERNS.items()}
        return {"api": api_id, "ok": True, "get_ops": n_get, "props": len(names), "hits": hits}
    except Exception as e:
        return {"api": api_id, "ok": False, "err": str(e)[:120]}


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    listing = get_json("https://api.apis.guru/v2/list.json", timeout=120)
    items = []
    for api_id, entry in sorted(listing.items()):
        v = entry["versions"].get(entry.get("preferred")) or next(iter(entry["versions"].values()))
        if v.get("swaggerUrl"):
            items.append((api_id, v["swaggerUrl"]))
    if limit:
        items = items[:limit]
    results = []
    with cf.ThreadPoolExecutor(16) as ex:
        for i, r in enumerate(ex.map(analyze, items), 1):
            results.append(r)
            if i % 200 == 0:
                print(f"progress {i}/{len(items)}", flush=True)
    json.dump(results, open("authz_signal_survey.json", "w", encoding="utf-8"), ensure_ascii=False)

    def summary(label, rows):
        ok = [r for r in rows if r["ok"] and r["get_ops"] > 0]
        n = len(ok)
        if not n:
            return
        line = f"{label}: specs_with_GET={n}"
        for c in PATTERNS:
            k = sum(1 for r in ok if r["hits"][c])
            line += f" | {c} {k} ({100*k/n:.1f}%)"
        vs = sum(1 for r in ok if r["hits"]["VIS"] or r["hits"]["SHARE"])
        line += f" | VIS_or_SHARE {vs} ({100*vs/n:.1f}%)"
        print(line)

    print(f"total={len(results)} fetched_ok={sum(r['ok'] for r in results)}")
    summary("ALL", results)
    summary("EXCL_BIG_CLOUD", [r for r in results if not any(b in r["api"] for b in BIG)])
    from collections import Counter
    for c in PATTERNS:
        cnt = Counter(n.lower() for r in results if r["ok"] for n in r["hits"][c])
        print(c, "top:", cnt.most_common(12))


if __name__ == "__main__":
    main()
