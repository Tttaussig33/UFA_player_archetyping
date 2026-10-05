"""Validate the visible Shown Space comparison and prepare its source receipt."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
capture = json.loads((HERE / "shownspace_huck_comparison.json").read_text())
rows = capture["rows"]
nearby = capture["nearbyRows"]
assert len(rows) == len({r["player"] for r in rows}) == 8
assert len(nearby) == len({r["player"] for r in nearby}) == 18
for row in nearby:
    completed, denominator = map(float, row["huckCompletionRatio"].split("/"))
    assert abs(100 * completed / denominator - row["huckCompletionPct"]) <= 0.051
assert {r["player"] for r in rows} == {
    r["player"] for r in nearby
    if r["huckAttemptPct"] >= 10 and r["huckCompletionPct"] >= 70
}

columns = [
    {"field": "player", "label": "Player"},
    {"field": "team", "label": "Team"},
    {"field": "huckAttemptPct", "label": "Huck attempt (%)"},
    {"field": "huckCompletionPct", "label": "Huck completion (%)"},
    {"field": "huckCompletionRatio", "label": "Shown Space HuCP sample"},
    {"field": "games", "label": "Games"},
]
base_filters = [
    "Minimum games: 10",
    "Minimum offensive possessions: 10",
    "Minimum defensive possessions: 10",
    "Stat view: Per 100 Poss",
]
caveats = [
    "The 10% huck-attempt and 70% completion cutoffs are explicit analytical choices, not official Shown Space tiers.",
    "The comparison retains the user's 10-game minimum, so it does not include players with fewer games.",
    "Shown Space HuCP percentages and displayed completion ratios exclude dropped hucks from the denominator; they differ from the all-attempt completion percentages used in the earlier regular-season analysis.",
    "The 2026 season view is different from the earlier project's regular-season-only comparison.",
    "Displayed percentages are rounded to one decimal place. Small completion samples and differences in throw difficulty limit conclusions about underlying throwing ability.",
]
queries = []
for key, title, data, ap, cp in [
    ("huck-qualifiers", "Shown Space player rankings", rows, 10, 70),
    ("nearby-huck-candidates", "Shown Space nearby candidates", nearby, 8, 65),
]:
    queries.append({
        "id": key,
        "source": {
            "label": title,
            "url": capture["sourceUrl"],
            "files": ["analysis/shownspace_huck_comparison.json"],
            "executedAt": capture["capturedAt"],
            "filters": base_filters + [f"Minimum huck attempt: {ap}%", f"Minimum huck completion: {cp}%"],
            "metricDefinitions": [
                {"label": "HuAP%", "definition": "The share of a player's throws that are huck attempts."},
                {"label": "HuCP%", "definition": "Huck completion percentage as displayed by Shown Space, with its completion/sample ratio preserved."},
            ],
            "caveats": caveats,
            "evidenceFlow": [
                {"kind": "source", "title": "Source selection", "detail": "Read the user's open Shown Space player table in its 2026 season view. The initial maximum HuCP of 6% was replaced by a minimum to answer the high-completion question."},
                {"kind": "validation", "title": "Counts and thresholds", "detail": "All 18 displayed completion ratios reproduce their displayed percentages within rounding. Applying the main cutoffs to the expanded comparison reproduces exactly the eight main qualifiers."},
            ],
        },
        "rows": [{c["field"]: r[c["field"]] for c in columns} for r in data],
        "columns": columns,
        "reportingPeriod": "2026 season view",
        "capturedAt": capture["capturedAt"],
        "preview": {"kind": "aggregate", "note": f"All {len(data)} player rows returned by these filters; every table page was read.", "totalRows": len(data)},
        "methods": [{"language": "python", "code": "qualifiers = [r for r in nearby_rows if r['huckAttemptPct'] >= 10 and r['huckCompletionPct'] >= 70]\nfor r in nearby_rows:\n    completed, denominator = map(float, r['huckCompletionRatio'].split('/'))\n    assert abs(100 * completed / denominator - r['huckCompletionPct']) <= 0.051"}],
    })
payload = {
    "schemaVersion": 1,
    "items": [{
        "id": "shownspace-high-frequency-high-completion-huckers",
        "title": "Eight players meet both huck cutoffs; Atkins is a strong nearby comparison",
        "assumptions": ["High huck usage means at least 10% of throws are hucks, and high completion means at least 70% in the site's HuCP metric."],
        "queries": queries,
    }],
}
(HERE / "shownspace_huck_comparison_sources.json").write_text(json.dumps(payload, indent=2) + "\n")
print("Validated 8 qualifiers, 18 nearby candidates, and every displayed completion ratio.")
