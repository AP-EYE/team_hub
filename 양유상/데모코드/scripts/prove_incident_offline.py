"""Run only while the dedicated synthetic upstream is stopped; read-only proof."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway import store

ROOT = Path(__file__).resolve().parents[1]


def upstream_listening():
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(('127.0.0.1', 8811)) == 0


def database_snapshot():
    result = {}
    with store.connect() as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        for table in ('runs', 'events', 'findings', 'observations', 'model_results'):
            # Table names are a fixed literal list; no user data is interpolated.
            rows = connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
            payload = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str, separators=(',', ':'))
            result[table] = {'count': len(rows), 'sha256': hashlib.sha256(payload.encode()).hexdigest()}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    before_port = upstream_listening()
    if before_port:
        raise SystemExit('Upstream 8811 is still listening; no offline claim can be made.')
    before = database_snapshot()
    with httpx.Client(base_url='http://127.0.0.1:8810', timeout=30, trust_env=False) as client:
        params = {'run_id': args.run, 'actor': 'bob'}
        full_response = client.get('/api/incidents/analyze', params=params)
        full_response.raise_for_status()
        full = full_response.json()
        metadata_response = client.get('/api/incidents/analyze', params={**params, 'capture': 'metadata_only'})
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        export = client.get('/api/incidents/report', params=params)
        export.raise_for_status()
    after, after_port = database_snapshot(), upstream_listening()
    checks = [
        {'name': 'synthetic_upstream_offline_before_and_after', 'pass': not before_port and not after_port},
        {'name': 'full_analysis_http_200', 'pass': full_response.status_code == 200},
        {'name': 'metadata_analysis_http_200', 'pass': metadata_response.status_code == 200},
        {'name': 'markdown_export_http_200', 'pass': export.status_code == 200 and export.text.startswith('# ')},
        {'name': 'all_source_tables_byte_fingerprints_unchanged', 'pass': before == after},
        {'name': 'no_analysis_replay', 'pass': full.get('network_replay') is False and metadata.get('network_replay') is False},
        {'name': 'same_call_count_without_response', 'pass': full['summary']['logged_requests'] == metadata['summary']['logged_requests'] == 13},
        {'name': 'metadata_exposure_unknown', 'pass': metadata['summary']['confirmed_exposure_subjects'] is None},
    ]
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'run_id': args.run,
        'scope': 'Synthetic upstream 8811 was stopped; gateway 8810 and PostgreSQL remained running. Analysis/export used existing logs only.',
        'upstream_listening_before': before_port, 'upstream_listening_after': after_port,
        'source_before': before, 'source_after': after, 'full_summary': full['summary'], 'metadata_summary': metadata['summary'],
        'checks': checks, 'passed': sum(row['pass'] for row in checks), 'total': len(checks)}
    report['status'] = 'PASS' if report['passed'] == report['total'] else 'FAIL'
    out = ROOT / 'evidence'
    (out / 'incident-offline-proof.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'incident-offline-report.md').write_text(export.text, encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    store.close()
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
