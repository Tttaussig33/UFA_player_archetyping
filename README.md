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

- Choose any team or **League leaders** in the left rail.
- The default is the full available **regular season**, with both O-line and D-line events.
- Each box shows its aEC leader. Select a box for every recorded vector for that player in that zone.
- **Player boxes** restores the full portrait map; **Disc vectors** shows the selected player’s events.
- **Play zones** automatically cycles the 12 zones. Selecting a player or zone stops the tour.
- The zone ranking lets you inspect other players, including the full list beyond the first seven.
- Filter to completed passes or turnovers/drops; inspect the underlying event records below the field.
- **Save field SVG** exports the current field, including embedded portraits. **Export events** saves exactly the displayed player/zone/outcome event population to CSV.
- Open the earlier [possession browser](https://tttaussig33.github.io/frisbee-analytics/) from the sidebar.

The field is deliberately compact enough to see all zones at once. **Enlarge field**, browser zoom
or the SVG export provides a larger view. Green lines are completions; red lines
are turnovers/drops; purple lines are Callahan interceptions. These are **disc-flight
vectors, not tracked player movement**.

## Relationship to the reference

The Instagram post was inspected directly, including its animated vectors and the
author’s explanation that main-field dots represent throwing locations and end-zone
dots represent receiving locations. The reproduced geometry is eight throwing
zones, three attacking-end-zone receiving zones, and a defensive Callahan panel.

Zone boundaries are inferred from the drawing, not obtained from the author’s
source code: x = −15 and +15 yards define the central lane; the throwing field
runs from y = 20 to 100; central bands break at 40, 60 and 80; side lanes break at
60. The front scoring end zone spans y = 100–110 and splits at x = 0. The deep end
zone spans y = 110–120. The field width is 53.3 yards.

This is a later 2026 snapshot, so it is **not a promise to reproduce the July 10
post’s historical rankings**. This version supplies the spatial exploration layer;
it does not yet assign learned player-archetype or clustering labels.

## Data and metric definitions

The project imports the previous frisbee-analytics possession-browser cache and
preserves an independent copy in `data/raw/`. Read-only public Shown Space API
responses supply schedule metadata, names, portrait URLs, missing-game checks,
new playoff games and Callahan defenders. They are preserved in `data/source-api/`.
No changes were made to the earlier project.

- **78,847 unique throws**, covering 142 games with available throws.
- **72,663 regular-season throws**, covering 131 of the 132 regular-season entries.
- **6,184 playoff throws**, covering 11 entries with available throws.
- **669 player portraits** are stored locally. Players without a portrait use initials.
- Eighteen throws lack aEC. They remain in counts and vectors, but are omitted from aEC sums.
- Source player ID `unknown` is retained in event records and excluded from player rankings.

For a completed pass, the supplied event aEC is credited in full to both its
thrower and receiver. For a drop, the receiver takes the aEC and the thrower gets
zero. For other turnovers, the thrower takes the aEC and no receiver is credited.
The UI sums those role-specific credits within each zone; it does not estimate
or retrain Shown Space’s model. Completion rate is completions/all throws; catch
rate is catches/(catches + recorded drops).

Callahans are matched to a unique opposite-side throwing event in the same game,
quarter and point. The panel credits the named defender with the negative of the
intercepted throw’s aEC, reconstructing the video’s convention. This reproduces
Josh Klane’s two interceptions and 1.86 aEC in the reference. Defensive credit is
kept separate from offensive thrower/receiver totals.

Every offense attacks toward y = 120 in the supplied coordinates. Normal throws
from y < 20 are outside the reference’s eight main-field throwing zones. A source
coordinate rounded up to 0.02 yards beyond a sideline is drawn on that sideline;
the original coordinates remain in source rows and CSV exports. Shared zone
edges are assigned exactly once per role. Equal aEC totals break ties by event
count, then player ID.

### Coverage caveats

Shown Space returned no throws for July 18 Pittsburgh–Chicago. Chicago and
Pittsburgh therefore each have 11 games of regular-season throws. The app displays
this gap when either team or the whole league is selected.

The schedule also includes empty July 17 Indianapolis–Pittsburgh and August 27
Oakland–New York entries outside the regular season. A separate August 27
New York–Oakland entry has data. These entries are preserved as listed; none is
silently turned into zero-valued player performance or treated as a played game.

See `data/validation.json` for coverage and reconciliation results and
`data/source-manifest.json` for hashes of the files used.

## Development

- `src/content/dashboard/`: authored React, field geometry, ranking logic and CSS.
- `src/data.json`: reviewed data and provenance snapshot.
- `tools/build_dataset.py`: reproducible standard-library Python transformation.
- `tools/fetch_portraits.py`: downloads only public URLs supplied by Shown Space.
- `tools/model.test.mjs`: zone-edge, population, missing-value and reconciliation tests.
- `dist/`: complete built browser app and its required data sidecar.

Run `python3 tools/build_dataset.py` to reconstruct the dataset from the preserved
inputs. Run `node --test tools/model.test.mjs` for analytical tests. The Data app’s
`AGENTS.md` documents how to rebuild authored React using the installed Data plugin;
do not modify its protected runtime to change the analysis.

The checks performed for this version include all 22 team maps, all six analytical
tests, 2,304 supplied per-game player-metric reconciliations (largest numerical
difference below 1e-8), and browser checks of throwing, receiving, Callahan,
team/league selection, season/line filtering, playback, export and responsive layout.

Sources: [Shown Space](https://shownspace.com/),
[metric explanation](https://shownspace.com/about),
[2026 league schedules](https://www.server.watchufa.com/league/news/2026-ufa-team-schedules-announced).
