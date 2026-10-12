"""Preserve a dated copy of five DBeaver exports and select it for the builder."""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from database_exports import TABLES, csv_rows, sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--snapshot', required=True, help='YYYY-MM-DD date appearing in the export filenames')
    parser.add_argument('--season', type=int, default=2026, choices=[2026], help='The current dashboard is scoped to 2026.')
    args = parser.parse_args()
    date = datetime.strptime(args.snapshot, '%Y-%m-%d').strftime('%Y%m%d')
    destination = ROOT / 'data/database-exports' / args.snapshot
    destination.mkdir(parents=True, exist_ok=True)
    entries = {}
    for table in TABLES:
        candidates = sorted(args.source_dir.glob(f'{table}_{date}*.csv'))
        if len(candidates) != 1:
            raise ValueError(f'Expected one {table} export for {args.snapshot}, found {len(candidates)}')
        source = candidates[0]
        target = destination / f'{table}.csv'
        digest = sha256(source)
        if target.exists() and sha256(target) != digest:
            raise ValueError(f'Refusing to overwrite a different preserved export: {target}')
        rows = sum(1 for _ in csv_rows(source, table))
        if not rows:
            raise ValueError(f'{table} export is empty')
        if not target.exists():
            shutil.copy2(source, target)
        if sha256(target) != digest:
            raise ValueError(f'Copy verification failed: {table}')
        entries[table] = {'file': target.name, 'originalFilename': source.name,
                          'sha256': digest, 'rows': rows, 'bytes': target.stat().st_size}
    manifest = {'snapshot': args.snapshot, 'importedAt': datetime.now(timezone.utc).isoformat(),
                'source': 'User-exported CSVs from postgres.prod through DBeaver',
                'tables': entries,
                'caveats': ['Export row counts have not been compared with a live database query.']}
    manifest_path = destination / 'manifest.json'
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous['tables'] == entries:
            manifest['importedAt'] = previous['importedAt']
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    selection = {'manifest': str(manifest_path.relative_to(ROOT)), 'season': args.season}
    (destination.parent / 'current.json').write_text(json.dumps(selection, indent=2) + '\n')
    print(json.dumps({'selected': selection, 'tables': entries}, indent=2))


if __name__ == '__main__':
    main()
