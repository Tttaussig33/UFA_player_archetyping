"""Import explicit film-review checkbox choices without editing pass labels.

Run before recalculating comparisons after collecting a new browser export.
Changing this registry invalidates the analysis hashes until it is rebuilt.
"""
from pathlib import Path
import argparse
import csv
import json

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('review_export', type=Path)
    args = parser.parse_args()
    export = json.loads(args.review_export.read_text())
    path = ROOT / 'special_situation_exclusions.json'
    registry = json.loads(path.read_text())
    by_id = {r['possessionId']: r for r in registry['possessions']}
    with (ROOT / 'possessions.csv').open() as handle:
        source = {r['possession_id']: r for r in csv.DictReader(handle)}
    changed = []
    for review in export['reviews']:
        flag = review.get('endOfQuarterAttempt')
        if not isinstance(flag, bool):
            continue
        pid = review['possessionId']
        assert pid in source, 'Review does not match the preserved possession cohort.'
        previous = by_id.get(pid)
        if previous and (previous.get('reviewedOn') or '') > (review.get('reviewedOn') or ''):
            continue
        if previous and previous['excludeFromTypicalOline'] == flag:
            continue
        if not previous and not flag:
            continue
        row = source[pid]
        by_id[pid] = {**(previous or {}), 'caseId': review['caseId'],
                     'possessionId': pid, 'gameId': row['GameID'],
                     'quarter': int(row['quarter']),
                     'reason': 'end_of_quarter_scoring_attempt',
                     'excludeFromTypicalOline': flag,
                     'source': 'Explicit film-review checkbox',
                     'reviewExport': str(args.review_export.resolve()),
                     'reviewedOn': review.get('reviewedOn'), 'preserveFilmLabels': True}
        changed.append(pid)
    if changed:
        registry['possessions'] = list(by_id.values())
        path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'changedPossessions': changed,
                      'rawReviewExportUnchanged': True,
                      'recalculateComparisons': bool(changed)}))


if __name__ == '__main__':
    main()
