"""Export a bounded investigation from PostgreSQL, without API or model replay."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gateway import incident, store


def filename_part(value):
    """Keep user-supplied filters out of filesystem path semantics."""
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('._-')[:100] or 'scope'


def export(report, capture):
    created = datetime.now(timezone.utc)
    stamp = created.strftime('%Y%m%dT%H%M%S%fZ')
    suffix = uuid4().hex[:8]
    filename = '-'.join((filename_part(report['run']['id']), filename_part(report['actor']), capture, stamp, suffix))
    output = ROOT / 'evidence' / 'incidents'
    output.mkdir(parents=True, exist_ok=True)
    json_path, md_path = output / (filename + '.json'), output / (filename + '.md')
    report = {**report, 'export': {'generated_at': created.isoformat(), 'tool': 'scripts/export_incident.py'}}
    # Exclusive creation preserves every previous export and the original records.
    with json_path.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    with md_path.open('x', encoding='utf-8') as handle:
        handle.write(incident.markdown(report) + '\n')
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, help='Existing stored run ID; this command never creates a run')
    parser.add_argument('--actor', default='bob', help='Stored account name, or all')
    parser.add_argument('--capture', choices=('full', 'metadata_only'), default='full')
    parser.add_argument('--start', help='Inclusive ISO-8601 time with timezone, for example 2026-09-22T12:04:03+09:00')
    parser.add_argument('--end', help='Inclusive ISO-8601 time with timezone')
    args = parser.parse_args()
    try:
        report = incident.analyze(args.run, actor=args.actor, start=args.start, end=args.end, capture=args.capture)
        json_path, md_path = export(report, args.capture)
    except (ValueError, LookupError) as error:
        parser.error(str(error))
    finally:
        store.close()
    print(json.dumps({'source': report['source'], 'network_replay': report['network_replay'],
        'run_id': report['run']['id'], 'actor': report['actor'], 'analysis_mode': report['analysis_mode'],
        'summary': report['summary'], 'json': str(json_path), 'markdown': str(md_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
