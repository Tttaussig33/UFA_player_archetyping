# UFA player archetyping

Explore one practical question: **What does this player tend to throw, and how
successful are those throws?** The main throwing profile uses original Shown
Space aEC and lag contribution, plus pass counts and completion rates. The
original field-zone map and passing connections remain available for all 22 teams.

## Terminology

Use **throwing location** or **throwing locations**, rather than “release
location(s),” in future explanations, reports and interface labels. This means
the position on the field from which a player throws the disc.

## Open the project

Double-click **Open UFA player archetyping.command**. It starts a local-only web
server and opens the explorer. Keep its Terminal window open while using it;
Control-C stops the server. Python 3 is the only requirement for opening the built app.

Alternatively, from this folder:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory dist
```

Then open <http://127.0.0.1:4173>.

## Explore

- **Throwing profiles:** search any of the 747 named throwers with recorded 2026
  passes. The season row shows Shown Space's original **thrower aEC** and
  **lag contribution**, plus **Completion %** from completed / attempted passes
  in the export, including playoffs and all lines. Drops are incomplete; this
  keeps the existing completion calculation, not the adjusted leaderboard CP%. They stay fixed when
  selecting a group of throws. There is no minimum-attempt qualification or
  custom player-quality score.
- Choose **Throw length** or **Throw direction**. Bars/slices show how many throws
  the player attempted, including incompletions. Select a length directly, or a
  direction followed by **Inspect throws**, to open the matching throw records and scroll to them.
  **Show all throws** opens the full list and clears the selection. Completion for a length or direction
  is available on hover; the season row stays fixed. Expand **Inspect these throws**
  for the exact records and individual aEC values.
- Length means straight-line distance between recorded throw and target locations.
  The four display ranges are 0–<10, 10–<20, 20–<40 and 40+ yards; these are not
  learned archetypes or the huck definition. Direction keeps Shown Space's twelve
  30-degree bins, with forward up and positive 90° left. Stationary passes have no
  spatial direction and are omitted only from the direction view. Stalls are omitted
  from both charts, but retained in source season aEC.
- **Connections:** search a player, then explore incoming and outgoing partners.
  Filter to all passes or hucks, and to completed passes or all attempts. The team,
  season-phase and line controls apply here and in Field views.
- **Field views:** choose a team or League leaders. **Original** preserves the
  Instagram layout; **Thrower aEC**, **Receiver aEC** and **Overall aEC** use all
  twelve boxes. Select a box to see its players, disc vectors and records. The
  bottom panel can show Callahans separately. Field SVG and event CSV exports
  follow the selected view.
- Use the **sun/moon icon** to switch light and dark mode. Source definitions,
  evidence and original rows remain accessible from each section's menu.

Throwing profiles covers the **full available 2026 season including playoffs**.
The other tabs' team, phase and line filters do not silently restrict that profile.
The previous contribution categories, similarity scores, research diagnostics and
separate deep-thrower/radial pages are removed from navigation. Old radial and
deep-thrower tab links open the simpler profile; historical code and evidence are
retained for reproducibility.

**Field guide**, available in Field views and Connections, explains throwing
location, forward gain, straight-line distance and the huck thresholds with an
interactive illustration. Disc-flight vectors do not show tracked player movement.

## Relationship to the reference

The Instagram post was inspected directly, including its animated vectors and the
author’s explanation that main-field dots represent throwing locations and end-zone
dots represent receiving locations. The reproduced geometry is eight main-field
zones, three attacking-end-zone zones, and one own-end-zone panel. **Original**
preserves that mixed-role layout. The full-field **Thrower aEC** and **Receiver aEC**
views extend it so every zone supports either metric; **Overall aEC** combines both roles per player. Callahans are also available
as a separate bottom-panel option in those views.

Zone boundaries are inferred from the drawing, not obtained from the author’s
source code: x = −15 and +15 yards define the central lane; the throwing field
runs from y = 20 to 100; central bands break at 40, 60 and 80; side lanes break at
60. The front scoring end zone spans y = 100–110 and splits at x = 0. The deep end
zone spans y = 110–120. The field width is 53.3 yards.

This is a later 2026 snapshot, so it is **not a promise to reproduce the July 10
post’s historical rankings**. This version supplies the spatial exploration layer;
historical grouping studies remain in the repository, not in the simplified profile.

## Historical archetype and replacement pilot

The executed [research notebook](analysis/archetype_candidate_validation.ipynb)
documents the first tests of discrete style groups, repeatable passing performance,
and cross-team comparison candidates. The saved results and implementations are
`analysis/archetype_candidate_validation.json` and `.py`.

- Both 2024→2025 and 2025→2026 tests prefer two broad groups over 3–6 groups.
  These mainly describe relative backfield/upfield activity; they are not deep-thrower
  versus short-pass archetypes. In the 2026 test, 126/146 players (86.3%) remained in
  the same group across halves. Chance-adjusted agreement was 0.524, below the
  chosen 0.60 pilot threshold; 2025 also missed it. The cutoff is a research choice,
  not proof that useful archetypes cannot exist.
- Adding prior-year player passing-performance offsets to a geometry + prior-team
  baseline reduced later Brier error by only 0.058% in 2025 and increased it by
  0.020% in 2026. Game- and player-bootstrap intervals include zero. This simple
  model has not validated a transferable passing rating; this is not evidence
  that player skill is unimportant.
- As a concrete style/performance distinction, Alex Atkins's nearest cross-team
  match is Henry Goldenberg. Their recorded regular-season huck completions are
  28/35 and 7/16 respectively. Differences in difficulty and the smaller sample
  still matter. No lineup replacement intervention or outcome was tested.

Reproduce with Python + NumPy/pandas (no live database connection):

```sh
python3 analysis/archetype_candidate_validation.py
python3 analysis/archetype_candidate_checks.py
python3 analysis/build_archetype_candidate_notebook.py
python3 tools/player_profiles.py
```

The notebook executes every cell and embeds two SVG figures. Its default uses
the saved full model result and reruns independent CSV/numerical checks; set
`RECOMPUTE=True` in the notebook to rerun all models and bootstraps there.
The profile importer verifies source hashes, and the normal dataset rebuild
attaches these queries when the same reviewed export/season is selected. New
source exports require rerunning the study before attaching its results. All
existing event, radial and connection queries remain separate.

## Data and metric definitions

The simple throwing profile's original season totals are preserved in
`data/source-api/leaderboard-2026-2026-11-03.json`, retrieved from Shown Space's
2026 public leaderboard. `tools/throwing_focus.py` imports `thrower_aec` and
`lag_contribution` without recalculating either and records the endpoint, capture
time and file hash. All 747 imported aEC totals reconcile to the event export,
including stalls, within 1e-7. Eight players have different attempt counts in the
summary and export; five also differ in completion counts. The page discloses
those differences for the selected player and uses individual exported records
for the charts. LC remains a season total; it is never invented for a pass group.

Rebuild those source summaries with `python3 tools/throwing_focus.py`. Verify the
source reconciliation, length boundaries, direction orientation, missing-data
handling and every player's plotted groups with
`node --test tools/throwing-focus.test.mjs`. The normal dataset rebuild also
attaches these summaries.

The following radial details document the **historical reproduction**. The new
Throw direction view uses the same bins but positions them in their actual field
direction and removes zero-distance throws.

Radial grouping is preserved in `data/database-metadata/2026-10-12/`, including
the read-only database function and Alex Atkins verification output. His full
2026 snapshot reconciles to all twelve buckets, 552 throwing events and 469
receiving targets. The original profile’s rendered SVG was inspected on October
14, 2026: it places 0° at the top, increases angles clockwise, centers wedges on
their bucket’s lower-edge label and scales radial length from a small central
hole. Receiving uses the same flight angle without rotation. These reproduce the
source’s display convention; the sector’s exact numeric interval is shown in its
tooltip. Percentages divide by the selected role’s events with recorded angles.
Missing angles are excluded, never reconstructed from coordinates. The model and
source metadata survive future local snapshot rebuilds; tests live in
`tools/radials.test.mjs`.

The current app uses the October 12, 2026 DBeaver exports of `prod.throws`,
`prod.games`, `prod.players`, `prod.teams`, and `prod.blocks`. Full, unmodified
copies are in `data/database-exports/2026-10-12/`; `manifest.json` records their
original filenames, row counts, sizes and SHA-256 hashes. `current.json` selects
the snapshot and the app's 2026 season. These files support offline rebuilding;
the website makes no database connection and contains no database credentials.

The saved exports include 490,688 throws and 17,508 blocks across 2021–2026,
plus 2,059 game rows, 10,399 roster rows and 297 team-season rows. The app still
shows 2026, while all other exported seasons remain available locally. The full
CSV files are excluded from Git and publication; keep them when backing up the
project. They have been checked locally, not compared with a live database count.

The earlier possession-browser cache remains in `data/raw/` and the historical
public API responses remain in `data/source-api/`. They supply existing portrait
URLs and historical aggregate checks, but cannot override imported event, game,
name, team or defender records. No changes were made to the earlier project.

- **78,847 unique throws**, covering 142 games with available throws.
- **72,663 regular-season throws**, covering 131 of the 132 regular-season entries.
- **6,184 playoff throws**, covering 11 entries with available throws.
- **669 player portraits** are stored locally. Players without a portrait use initials.
- **826 distinct named 2026 roster players** are available. Seven repeated player
  IDs share one display identity after their names agree; one blank-ID roster row
  is skipped. Active flags do not remove players' historical events. The source
  roster rows are not joined directly onto throws, avoiding duplicated passes.
- Eighteen throws lack aEC. They remain in counts and vectors, but are omitted from aEC sums.
- Source player ID `unknown` is retained in event records and excluded from player rankings.

For a completed pass, the supplied event aEC is credited in full to both its
thrower and receiver. For a drop, the receiver takes the aEC and the thrower gets
zero. For other turnovers, the thrower takes the aEC and no receiver is credited.
The UI sums those role-specific credits within each zone; it does not estimate
or retrain Shown Space’s model. Completion rate is completions/all throws; catch
rate is catches/(catches + recorded drops). Overall aEC adds each player’s throwing
and receiving credits within the same box. Role counts are throws plus targets; a
completed pass may credit two different players, while source inspection retains
the underlying pass once. Overall aEC is player-role contribution, not unique
possession value. Circles/solid arrows mark throws; squares/dashed arrows mark
receptions in the combined view.

Callahans are matched to a unique opposite-side throwing event in the same game,
quarter and point. The panel credits the named defender with the negative of the
intercepted throw’s aEC, reconstructing the video’s convention. This reproduces
Josh Klane’s two interceptions and 1.86 aEC in the reference. Defensive credit is
kept separate from offensive thrower/receiver totals.

Every offense attacks toward y = 120 in the supplied coordinates. In the full-field
views, ordinary throws and receptions at 0 ≤ y < 20 appear in the bottom own-end-zone box. Each event
is assigned once per metric: by its release for throwing and by its catch/drop
location for receiving. All y bands include their lower edge and exclude their
upper edge, except y = 120 is included in the deep end zone. Thus y = 20 enters
the main field and y = 100 enters the attacking end zone for either metric. A source
coordinate rounded up to 0.02 yards beyond a sideline is drawn on that sideline;
the original coordinates remain in source rows and CSV exports. Shared zone
edges are assigned exactly once per role. Equal aEC totals break ties by event
count, then player ID.

Original preserves the first adaptation’s boundary convention: releases at exactly
y = 100 remain in the main-field throwing zones, and catches/drops at y = 100
enter the front receiving zones. A pass can contribute to both a throwing box and
a receiving box; source inspection lists each underlying pass only once. Ordinary
own-end-zone throws and receptions are available in the full-field views.

### Coverage caveats

The database export contains no throws for July 18 Pittsburgh–Chicago. Chicago and
Pittsburgh therefore each have 11 games of regular-season throws. The app displays
this gap when either team or the whole league is selected.

The schedule also includes empty July 17 Indianapolis–Pittsburgh and August 27
Oakland–New York entries outside the regular season. A separate August 27
New York–Oakland entry has data. These entries are preserved as listed; none is
silently turned into zero-valued player performance or treated as a played game.

See `data/validation.json` for coverage and reconciliation results and
`data/source-manifest.json` for hashes of the files used.

The import preserved all 78,847 existing 2026 event IDs and their chart values
(numeric comparison tolerance 1e-12). The 28 Callahan records still reconcile.
Snapshot import time describes local processing, not a fresh model run or newly
played games.

### Refresh from another DBeaver export

Export all five tables to a directory with DBeaver's names such as
`throws_202610121011.csv`. Use the date appearing in those filenames:

```sh
python3 tools/import_database_exports.py --source-dir /path/to/exports --snapshot 2026-10-12 --season 2026
python3 tools/build_dataset.py
```

The importer requires one file per table for that date and refuses to overwrite
a different preserved snapshot. The builder verifies the recorded hashes and
fails if an imported file is missing or changed. It does not silently fall back
to older API data. Follow `AGENTS.md` to build and verify the updated app, then
set `buildStatus` to `complete` and rebuild before delivery.

### Possession and radial fields

The imported event rows preserve `point`, `possession`, `possessionThrow` and
`eventSequence`, corresponding to `quarter_point`, `possession_num`,
`possession_throw` and `global_event_seq`. They are game-context fields, not
league-wide identifiers. Their presence does not establish a hypothetical
cross-team possession or a unique team-level aEC formula.

The input for throw-direction radial diagrams is in `prod.throws`: `Thrower`,
`Receiver`, `throw_angle`, `throw_distance`, `x_diff`, `y_diff`, `ThrowerX/Y` and
`ReceiverX/Y`. The reviewed event aliases are `throwAngle`, `throwDistance`,
`xDiff`, `yDiff`, `tx/ty` and `rx/ry`. The numeric source values are preserved;
no radial angle is reconstructed by this import.
`cp`, `cpoe` and `ec` are also preserved as supplied. Chart images are not part of
these five CSV exports. The separate Throw radials implementation uses the verified
database function and display convention described above.

## Development

The active simplified profile is `src/content/dashboard/ThrowingFocus.jsx`, with
`throwing-focus-model.js` and `throwing-focus.css`. Historical deep-thrower,
contribution and style-matching modules remain on disk but are not mounted by the
current navigation. The sections below retain their methods for reproducibility.

### Deep thrower profiles

`deep-thrower-model.js`, `DeepLeaderboard.jsx`, `DeepSetups.jsx` and `DeepThrowers.jsx` implement
the Deep throwers leaderboard and on-demand profiles. The leaderboard pools
counts for its scope baseline, retains the same 0–100% color scale across zones,
and sorts eligible players by the chosen location. Its source includes all
named throwers before sample/completion/search filters; derived display rows contain the
full matching player/zone leaderboard and baseline, not just the current page.
The huck definition is shared with Connections: flight >40 yards, downfield gain
>30 yards and no stall. Huck share divides by non-stall throws with usable
endpoint coordinates. Completion includes drops and unnamed targets. Individual pass
records and exports retain the supplied thrower aEC.

Prior-pass links require the same game, team, quarter, point and possession,
consecutive `possessionThrow`, unique order/sequence keys, increasing
`eventSequence`, a completed non-stall prior pass, and a prior receiver equal to
the current thrower. The join runs within the page-filtered population. It does
not infer routes, upline/swing labels, dead-disc starts, time-to-throw or the huck
receiver's location at release. Catch and release coordinates remain distinct.

Incoming-pass groups use the verified prior vector: forward when `dy > abs(dx)`,
backward when `-dy > abs(dx)`, and lateral otherwise for nonzero distance.
Exact 45-degree boundaries are lateral. Missing links/coordinates and zero-distance
passes stay unclassified. Huck choice divides huck attempts by non-stall next throws
with usable endpoints in the group; catches without a recorded next throw are not
included. Huck completion divides completed hucks by attempts in that same group.
The release-location filter uses the current throw origin. Original sources include
both next throws and their verified preceding passes. These descriptive groups are
not cutting routes or causal estimates; setup details can be inspected and exported.

The strict `>40` / `>30` definition was supplied by the user on October 22, 2026.
Replacing the former inclusive cutoffs removes no throws from the current snapshot.

The imported full-2026 data has 3,778 geometrically identified huck attempts;
3,406 have a verified preceding catch under these rules. Alex Atkins reconciles
to 53 attempts, 45 completions and 44 linked catches; restricting to the regular
season gives 28 completions. These checks, boundary/missing-data cases and
sequence ambiguity tests live in `tools/deep-throwers.test.mjs`.

Release tooltips show 95% Wilson completion intervals. They describe binomial
sampling uncertainty, without adjustments for player/game dependence, and do
not establish causal location effects or pairwise significance. The default
five-attempt zone minimum is an exploration aid, not a reliability guarantee.
Source metadata and definitions are regenerated by `add_deep_thrower_metadata`
in `tools/build_dataset.py`. Source inspection preserves original events;
sequence exports contain one row per huck plus verified preceding-pass fields.

### Connections tab

The Connections tab recreates the incoming-player → selected-player → outgoing-player
diagram with the existing 2026 throw snapshot. Search players by name or team across
the full reviewed roster. Choosing a player from another team updates the team
filter; the All teams view stays unrestricted. Season, line and pass filters stay
selected, with an explicit empty state when that player has no matching passes.
All passes preserves the general connections view;
Hucks only requires more than 40 yards of straight-line flight and more than 30 yards of forward gain from
the recorded coordinates and filters both sides of the diagram.

Completed passes is the default. All pass attempts also shows dropped and other
incomplete passes; unnamed targets remain visible as Unrecorded player. Stalls
are excluded. The two sides count separate events, not a single possession or an
inferred three-player sequence. Top 5/10 retain every remaining partner in Other
players, and All partners expands the full set. Selecting a link opens its exact
pass records, including flight and downfield distance, with a matching CSV export.

Run `node --test tools/connections.test.mjs` for huck thresholds, attribution,
grouping, link-detail scope, empty scopes and reconciliation across all teams.

### Historical huck validation

`analysis/multiseason_release_validation.ipynb` contains the executed 2021–2026
release-zone analysis and the October 25 incoming-pass follow-up. The latter
tests whether a verified preceding pass improves later-season huck-attempt
forecasts beyond player history and release position. The primary 2026 cohort
has 6,173 passes, 590 hucks and 44 players with at least 40 earlier hucks in the
Y20–60 release window. Training uses only earlier seasons; the already-inspected
2026 season is an exploratory temporal check, not an untouched external test.

Adding direction reduces Brier prediction error by 0.65% versus player/position.
After controlling for whether a preceding pass is classifiable, the direction
increment is 0.37%, with a 95% game-bootstrap interval of −0.13% to +0.88%.
Earlier seasons and a broader cohort support a small general tendency, but
personal setup interactions do not establish additional predictive value.
These are relative prediction-error reductions, not completion-rate changes or
proof that a defensive tactic prevents goals. Prior-pass directions describe
disc movement; they do not identify upline routes or dead-disc situations.

The follow-up lives in `analysis/huck_setup_validation.py` and its aggregate JSON.
`analysis/huck_setup_checks.py` independently reconciles 72,590 2026 passes with
the website's sequence logic and tests ambiguous links and target leakage.
The source CSVs remain local under `data/database-exports/2026-10-12/`.

```sh
python3 analysis/huck_setup_validation.py
python3 analysis/huck_setup_checks.py --node /absolute/path/to/node
UFA_NODE=/absolute/path/to/node python3 analysis/build_multiseason_notebook.py
```

The final command executes both studies and rebuilds the existing notebook with
embedded figures. It requires Python with numpy/pandas and Node; no database
connection is needed.

### Offensive passing-profile viability

The executed [passing-profile notebook](analysis/passing_profile_validation.ipynb)
tests a broader research direction using ordinary passes as well as hucks:
**Which players have similar recorded offensive tendencies, and where do they
differ?** This October 26 pilot compares early and later regular-season profiles,
keeping playing style separate from effectiveness.

Nine traits cover pass choices, release locations, completed-catch locations and
throw/catch involvement balance. Scaling uses earlier data only, with equal
weight for those four groups. Completion rate, aEC, team identity and absolute
event counts are not similarity features. The primary 2026 test requires 100
throws and 100 completed catches in each period, across at least three games
per role; it evaluates 43 players against 81 earlier-qualified candidates.

On average, a later profile resembles its own earlier profile more than 90.9%
of other candidates (95% team-bootstrap interval 86.9–94.0%; random baseline
50%). The same player is the closest match for 10/43 players (23.3%, versus
1.2% random). A within-team comparison also supports individual persistence:
23/32 match themselves first, versus a 20.9% random expectation among their
qualified teammates. The 50-event sensitivity includes 146 players and yields
a similar 90.5% average self-similarity percentile. Earlier seasons and a
2025→2026 check also show persistence, with overlapping players and data.

An exploratory follow-up selected five similar players from other teams using
early profiles. Those peers averaged the 69.9th later-similarity percentile in
the primary sample (random expectation: 50th). This supports testing a comparison
tool, **not** claiming that players are interchangeable or that discrete
archetypes exist. The test selects frequently involved players and contains no
off-disc movement, playing-time exposure or lineup replacement outcomes.

The source is still the October 12 CSV snapshot; no live refresh was performed.
Actual game timestamps, including a rescheduled game, determine the split.
An independent CSV-reader audit reconciles 72,601 eligible 2026 events, 72,590
named throws, 67,820 named completed catches, all primary profiles, the similarity
rankings and the selected peers. The website is unchanged by this research pilot.

```sh
python3 analysis/passing_profile_validation.py
python3 analysis/passing_profile_checks.py
python3 analysis/build_passing_profile_notebook.py
```

The last command reruns the study and checks, saves the executed notebook with
two embedded figures, and generates a local HTML review under
`/tmp/ufa-profile-review/`. Python with numpy/pandas and the original local CSVs
are required. The aggregate results are in
`analysis/passing_profile_validation.json`; raw CSVs remain excluded from Git.

- `src/content/dashboard/`: authored React, field geometry, ranking logic and CSS.
- `src/data.json`: reviewed data and provenance snapshot.
- `tools/import_database_exports.py`: preserve and select dated local CSV exports.
- `tools/database_exports.py`: validate source hashes, season scope and roster identities.
- `tools/build_dataset.py`: reproducible standard-library Python transformation.
- `tools/fetch_portraits.py`: downloads only public URLs supplied by Shown Space.
- `tools/model.test.mjs`: zone-edge, population, missing-value and reconciliation tests.
- `dist/`: complete built browser app. Keep the full directory when copying a build.

Run `python3 tools/build_dataset.py` to reconstruct the dataset from the preserved
inputs. Run `node --test tools/model.test.mjs` for analytical tests. The Data app’s
`AGENTS.md` documents how to rebuild authored React using the installed Data plugin;
do not modify its protected runtime to change the analysis.

The sun/moon toggle uses narrowly authorized changes in `src/DataAppShell.jsx`
and `src/components/DataAppChrome.jsx`. `useDataApp()` exposes `appearance`,
`resolvedAppearance`, and `setAppearance`, using the existing owner/viewer
persistence. The resolved scheme makes the first toggle work even with a saved
System preference. The shell no longer offers the theme picker; both desktop and
mobile overflow menus respect that choice. Rebuild this version
with the installed Data plugin's `data-app.mjs build --project-dir <project> --source`
using the project-local locked dependencies. The prebuilt runtime does not include
this binding. Source builds produce a standalone HTML file; `--separate-data` is
not supported with `--source`. Keep the scoped protected-runtime manifest in sync
only through the authorization workflow in `AGENTS.md`.

The checks performed for this version include all 22 team maps, all six analytical
tests for the original build, plus full-field throwing/receiving coverage, attribution,
bottom-panel checks, and regressions for the restored Original view; 2,304 supplied per-game player-metric reconciliations (largest numerical
difference below 1e-8), and browser checks of throwing, receiving, Callahan,
team/league selection, season/line filtering, playback, export and responsive layout.

Sources: [Shown Space](https://shownspace.com/),
[metric explanation](https://shownspace.com/about),
[2026 league schedules](https://www.server.watchufa.com/league/news/2026-ufa-team-schedules-announced).
