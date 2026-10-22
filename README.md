# UFA player archetyping

An interactive starting point for studying UFA player roles through where players
throw and receive the disc. This first version recreates the field-zone/player-box
concept in [Shown Space’s Kings of the Field](https://www.instagram.com/p/Danlzl5SoUs/)
for **all 22 teams in the 2026 season**.

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

- Use the **sun/moon icon** above any tab to switch between light and dark mode. The icon shows the mode you can switch to, and your choice is saved between visits. The separate theme picker has been removed.
- Choose any team or **League leaders** in the left rail.
- The default is the full available **regular season**, with both O-line and D-line events.
- **Original** is the default field view: receivers in the attacking end zone, throwers in midfield, and Callahans in the bottom panel, matching the first Instagram adaptation.
- Switch to **Thrower aEC / Receiver aEC** above the field to use release locations or catch/drop locations across all 12 boxes. Both metrics include the bottom (own) end zone.
- **Overall aEC** is the fourth view. It adds each player’s thrower and receiver aEC in the same box and ranks players by that sum, across all 12 boxes. The detail panel shows both role totals; vectors, records, and CSV exports identify throwing versus receiving contributions.
- Each box shows its selected metric’s leader. Select a box for every recorded vector for that player in that zone.
- In the full-field views, the **Bottom end zone** menu can show **Callahan aEC** separately; choose the field metric again to return to ordinary throws or receptions. Original always uses Callahans at the bottom.
- **Player boxes** restores the full portrait map; **Disc vectors** shows the selected player’s events.
- **Play zones** automatically cycles the 12 zones. Selecting a player or zone stops the tour.
- The zone ranking lets you inspect other players, including the full list beyond the first seven.
- Filter to completed passes or turnovers/drops; inspect the underlying event records below the field.
- **Save field SVG** exports the current field, including embedded portraits. **Export events** saves exactly the displayed player/zone/outcome event population to CSV.
- Open the earlier [possession browser](https://tttaussig33.github.io/frisbee-analytics/) from the sidebar.
- **Throw radials** shows a searchable player’s throwing and receiving direction diagrams. It shares the team, season-phase and line filters with Field views and Connections. **Hucks only** uses the same distance thresholds as Connections; **Completed passes** excludes unsuccessful events.
- Radials default to **All recorded (original)** and twelve 30° buckets, matching `prod.get_player_throw_directions`. To compare with Shown Space’s 2026 profile, choose **All 2026**, **All lines**, and **All passes**. All recorded includes stalls and unsuccessful named targets, so receiving totals are not necessarily completed catches.
- Original radial scaling fits each diagram to its own largest bucket; **Shared percentage** gives both roles the same percentage scale. Hover or focus a wedge for exact counts and shares. Select it and choose **Inspect passes** to open its underlying events; CSV export follows that selection.
- **Deep throwers** opens on a leaderboard: one player per row, release zones across columns, and completion rates with completed/attempted counts. Click a zone heading or use **Rank location** to rank players there. **Rank by** switches between completion rate and attempt volume. Team selection is a compact filter on this tab; the other tabs retain their team rail. The selected team, season phase and line apply throughout.
- Select a player to open their detailed profile; **Back to leaderboard** restores the comparison. The paired fields show **where they receive** and **where they release successful hucks**. Receiving defaults to verified catches immediately before a huck; **All catches** includes every completed reception. Release maps can show completion rate or attempt count. Cells display counts as well as rates; zone areas differ, so counts are not a spatial density.
- **Player minimum** requires total hucks across all locations. Ranking a specific zone also requires **Zone minimum** attempts there. Small-sample cells remain hatched, and no-attempt cells show a dash. The scope baseline includes all named throwers before minimums and search. The player minimum affects only the leaderboard; the zone minimum also controls profile-map shading and the highest-observed-zone summary.
- **Completion filter** defaults to at least the scope average in the ranked location. Use 70%, 80%, or Any completion rate to change it. Attempt count is a sample/volume measure; it does not identify better throwers by itself. The baseline precedes all eligibility filters and search.
- In a player profile, **What happens after the incoming pass?** compares forward, lateral and backward prior passes. **Huck choice** uses all located next throws as its denominator; **Huck completion** uses only huck attempts. Filter by release location and inspect each group’s original passes. Unclassified setups remain separate.
- Select a field zone, then its **Inspect** action, to examine individual hucks below. **The pass before the huck** draws verified preceding passes and actual hucks, with pagination, original records and a CSV export containing event IDs and coordinates. Unmatched hucks remain included without a guessed setup.

The field is deliberately compact enough to see all zones at once. **Enlarge field**, browser zoom
or the SVG export provides a larger view. Green lines are completions; red lines
are turnovers/drops; purple lines are Callahan interceptions. These are **disc-flight
vectors, not tracked player movement**.

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
it does not yet assign learned player-archetype or clustering labels.

## Data and metric definitions

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
