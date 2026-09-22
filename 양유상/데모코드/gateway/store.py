import hashlib
import json
import os
import threading
import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DSN = os.getenv('DEMO_DATABASE_URL', 'postgresql://privacy_demo:synthetic-local-demo-only@127.0.0.1:15439/privacy_demo')
POOL = ConnectionPool(DSN, min_size=1, max_size=4, open=False, timeout=15, kwargs={"row_factory": dict_row, "connect_timeout": 15})
POOL_LOCK = threading.Lock()


def connect():
    with POOL_LOCK:
        if POOL.closed:
            POOL.open(wait=True, timeout=30)
    return POOL.connection()


def close():
    POOL.close()


def init():
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS runs (id text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(), mode text NOT NULL, status text NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS events (id bigserial PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(), run_id text, payload jsonb NOT NULL, sha256 text NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS findings (id bigserial PRIMARY KEY, run_id text, payload jsonb NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS observations (id bigserial PRIMARY KEY, event_id bigint REFERENCES events(id), run_id text, mode text, actor text, tenant text, namespace text, subject_id text, canonical text, label text, path text, confirmed boolean)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS model_results (id bigserial PRIMARY KEY, created_at timestamptz DEFAULT now(), event_id bigint REFERENCES events(id), payload jsonb NOT NULL)''')
        conn.execute('CREATE INDEX IF NOT EXISTS events_run_idx ON events(run_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS obs_join_idx ON observations(run_id,actor,tenant,namespace,subject_id)')


def checksum(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def new_run(run_id, mode):
    with connect() as conn:
        conn.execute('INSERT INTO runs(id,mode,status) VALUES(%s,%s,%s)', (run_id, mode, 'running'))


def finish_run(run_id, status='completed'):
    with connect() as conn:
        conn.execute('UPDATE runs SET status=%s WHERE id=%s', (status, run_id))


def save(event, finding, observations):
    with connect() as conn:
        row = conn.execute('INSERT INTO events(run_id,payload,sha256) VALUES(%s,%s,%s) RETURNING id,created_at', (event['run_id'], Jsonb(event), checksum(event))).fetchone()
        finding['evidence_ids'] = [row['id']]
        finding_id = conn.execute('INSERT INTO findings(run_id,payload) VALUES(%s,%s) RETURNING id', (event['run_id'], Jsonb(finding))).fetchone()['id']
        for ob in observations:
            conn.execute('''INSERT INTO observations(event_id,run_id,mode,actor,tenant,namespace,subject_id,canonical,label,path,confirmed) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (row['id'], event['run_id'], event['mode'], event['actor'], ob['tenant'], ob['namespace'], ob['subject_id'], ob['canonical'], ob['label'], event['path'], finding['verdict'] == 'confirmed'))
    return row['id'], finding_id


def save_model(event_id, payload):
    with connect() as conn:
        conn.execute('INSERT INTO model_results(event_id,payload) VALUES(%s,%s)', (event_id, Jsonb(payload)))


def state():
    with connect() as conn:
        runs = conn.execute('SELECT * FROM runs ORDER BY created_at DESC LIMIT 50').fetchall()
        latest = runs[0]['id'] if runs else ''
        events = conn.execute('SELECT * FROM events WHERE run_id=%s ORDER BY id', (latest,)).fetchall()
        findings = conn.execute('SELECT * FROM findings WHERE run_id=%s ORDER BY id', (latest,)).fetchall()
        # Strict same-run + same-actor + same-tenant + same-namespace join. Only confirmed
        # responses contribute to the attacker's observed combined exposure.
        links = conn.execute('''SELECT actor,tenant,namespace,subject_id, array_agg(DISTINCT canonical ORDER BY canonical) AS fields, array_agg(DISTINCT path ORDER BY path) AS endpoints, array_agg(DISTINCT event_id ORDER BY event_id) AS event_ids, count(DISTINCT path) AS endpoint_count FROM observations WHERE run_id=%s AND confirmed=true GROUP BY actor,tenant,namespace,subject_id HAVING count(DISTINCT path)>=2 ORDER BY tenant,subject_id''', (latest,)).fetchall()
        subjects = conn.execute('''SELECT count(*) AS n FROM (SELECT DISTINCT tenant,namespace,subject_id FROM observations WHERE run_id=%s AND confirmed=true) s''', (latest,)).fetchone()['n']
        total = conn.execute('SELECT count(*) AS n FROM events').fetchone()['n']
        model = conn.execute('SELECT m.* FROM model_results m JOIN events e ON m.event_id=e.id WHERE e.run_id=%s ORDER BY m.id', (latest,)).fetchall()
    return {"runs": runs, "events": [{**r['payload'], "id": r['id'], "created_at": r['created_at'].isoformat(), "sha256": r['sha256'], "integrity_ok": checksum(r['payload']) == r['sha256']} for r in events], "findings": [{**r['payload'], "id": r['id']} for r in findings], "links": [{**r, "subject_key": f"{r['tenant']}:{r['namespace']}:{r['subject_id']}", "member_ids": [r['subject_id']], "attacker_observed": True, "reason": "동일 실행·요청자·테넌트·회원 체계에서 비인가 응답에 실제 포함된 정보만 연결. 실명 재식별의 법적 확정 아님."} for r in links], "subjects": subjects, "total_events": total, "model_results": [{"id": r['id'], "event_id": r['event_id'], **r['payload']} for r in model]}
