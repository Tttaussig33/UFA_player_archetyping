"""Shared, auditable exclusions from typical O-line comparisons.

Keep the underlying event/cohort rows and their original possession numbers.
This is a reviewed-ID exclusion, not a clock threshold or an outcome filter.
"""
from functools import lru_cache
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / 'special_situation_exclusions.json'


@lru_cache(maxsize=1)
def registry():
    result = json.loads(REGISTRY.read_text())
    ids = [r['possessionId'] for r in result['possessions']]
    assert len(ids) == len(set(ids))
    assert all(r['reason'] == 'end_of_quarter_scoring_attempt' for r in result['possessions'])
    return result


def excluded_ids():
    return {r['possessionId'] for r in registry()['possessions'] if r['excludeFromTypicalOline']}


def filter_frame(frame):
    """Apply the same exclusion to possession or throw rows; never renumber."""
    return frame.loc[~frame.possession_id.isin(excluded_ids())].copy()


def metadata():
    with (ROOT / 'possessions.csv').open() as handle:
        by_id = {r['possession_id']: r for r in csv.DictReader(handle)}
    ids = excluded_ids()
    assert ids <= set(by_id), 'Exclusion refers to a possession outside this cohort.'
    selected = [by_id[pid] for pid in sorted(ids)]
    return {
        'version': registry()['version'],
        'registryPath': str(REGISTRY.relative_to(ROOT.parents[1])),
        'registrySha256': hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
        'calculationSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'excludedPossessions': len(selected),
        'sourceThrowsExcluded': sum(int(r['throws']) for r in selected),
        'sourceHucksExcluded': sum(int(r['hucks']) for r in selected),
        'possessionIds': sorted(ids),
        'coverage': 'Known reviewed special situations only. Remaining games have not all been screened for clock-driven attacks.',
        'rule': registry()['rule'],
        'rawRowsAndFilmLabelsPreserved': True,
        'numericClockCutoffSeconds': None,
    }


def verify_metadata(value):
    assert value == metadata(), 'Recalculate after changing the special-situation exclusions.'
