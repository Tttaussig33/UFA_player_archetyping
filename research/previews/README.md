# UFA research reports

Open any of the `.canvas.tsx` files in this folder in VS Code. They open
directly as rendered reports through the local **UFA Research Preview** extension.

- `UFA-dead-disc-first-pass.canvas.tsx` — throws after recorded stoppages.
- `UFA-pull-centering.canvas.tsx` — each team's most frequent centering recipient.
- `UFA-oline-regain-hucking.canvas.tsx` — **O-line offense after turnovers**: throw counts, huck timing, catches, scoring, and breaks after turnovers. The team view defaults to the 12 playoff teams and can show all 22. **Possession shown in tables** selects first, second, or exact third possessions in both team tables. The comparison option retains the original first / second / third-or-later view.
- `UFA-possession-review.canvas.tsx` — film-review queue with saved labels, optional notes, game links and review-progress charts.

The film reviewer now opens **New · 100 possessions**: 80 cases prioritized for
ambiguous pass geometry and 20 broader examples, spanning all 22 teams in the
existing 12-game library. All 100 are unreviewed opening possessions; 37 are
from first quarters and 63 from second quarters. They are ordered by game and
point so the user can keep the same recording open. Predictions stay hidden.
The selection is saved in `research/possession_review/pattern_review_batch_100_2026-11-13.json`;
`prepare_pattern_review.py` reproduces it without changing the frozen model or
original film library. This is a targeted definition-development sample, not a
representative model-accuracy or league-prevalence sample.

The 65 existing reviews and their notes remain available. **Completed · 12 clips**
returns to the previous pilot. The new set resumes at its first unfinished
example after reload; **Next unreviewed** returns to skipped examples. Approximate
95-second windows include a score, quarter clock and first-passer cue. They
have not all been replay-verified. Match those cues and use the wrong-play
option or corrected-time note if needed. The saved workflow preference is to
prepare a fresh set whenever the user reports finishing one.

The previous **Pilot · 12 clips** batch began with twelve
unreviewed opening possessions across five games: four from Indianapolis–Madison (a game
with no prior human opening labels), four randomly drawn from the other
available openings, and four cases the coordinate model found ambiguous.
Predictions are frozen in `research/possession_review/opening_classifier_pilot.json`
and hidden from the review form. The original 52 archived decisions, prior review sets,
dictation, exports and the progress bars remain available. Clip windows use
the existing timing estimates; match the first thrower and point before labeling.
The pilot preparation did not replay-verify every estimated window.

The review question now reads **Is there a completed centering pass?**, with
**Centering pass**, **No centering pass**, and **Cannot tell** as the classification
choices. A wrong-play option remains for alignment problems. The stored
`attack1` code is retained for compatibility and now displays as **No centering
pass**; it does not imply speed, aggression, or a downfield throw. A reset after
the pull catcher looks downfield and finds no option is no centering pass.
The Houston point-eight example (Jimmy Zuraw to Mark Turner) was explicitly
confirmed this way in chat and is saved separately from the frozen pilot's
52-review input archive. Its first throw stays counted. Current definitions
live in `research/possession_review/centering_definition.json`, and new chat
labels in `annotations/classifier-pilot-chat-confirmations.json` under that
folder. These labels appear in the reviewer and exports; no model was retrained
or league statistics recalculated. Missing footage stays **Cannot tell**.

The initial coordinate pilot uses 27 eligible human-reviewed openings from ten
games, excluding known brick and roller contexts and unresolved coordinate or
film-alignment cases. It tests each game using a model fitted to the other games.
It identifies 21 of 21 centering passes but only one of six immediate attacks;
the other five attacks are incorrectly called centering. These deliberately
selected development examples do not establish league accuracy. No predicted
centering labels have been used to subtract throws or revise research metrics.

Dropdowns, tables, charts and expandable methods work without a server or terminal.
Section 4 now has a **Table measure** selector beside **Possession shown in
tables**. It stays synchronized with the measure above the individual-team
chart, while the chart's team selector does not restrict the table. Team-table
header arrows toggle numeric high-to-low/low-to-high sorting or alphabetical
team order. Sorting uses unrounded values, keeps missing results last, and
preserves every row and its sample size. The all-possession view sorts each
possession column or its displayed change; the multi-measure first-to-subsequent
summary sorts on the subsequent value. Tables keep the existing appearance.
The label **Huck completion percentage** replaces **Actual huck catch rate**.
**Possessions with a huck (%)** remains distinct from **Huck attempt percentage**;
expandable explanations beside the table explain those denominators and the
95% uncertainty ranges. Uninformative bootstrap intervals from all-success or
all-failure groups display a dash, including a change interval when either
observed-rate group has that problem; the original saved estimates and ranges
remain intact. This interface update changes no analytical values.
The dead-disc and pull-centering reports retain their earlier research snapshots.
The O-line report was expanded on November 5–6, 2026 using the preserved data;
its calculation and validation files are in `research/oline_possessions/`.
On November 12, it gained two throw-count charts using the same 45 eligible
human-reviewed possessions. Both charts show blue bars for possessions ending
in a goal and gray bars for possessions ending in a turnover; bar height is
mean throws per possession. Chart 1 counts every physical throw. Chart 2 subtracts one only
from possessions with a confirmed opening centering pass, keeps all other
counts unchanged, and recomputes the mean over the same possessions. Neither
chart drops a possession because it has a centering pass. Subsequent counts
therefore stay unchanged. Each possession group has one goal bar and one
turnover bar, with the outcome-specific sample sizes shown below each chart.
Later huck ordinals shift down one only after a confirmed opening centering
pass, and original starting coordinates remain unchanged. The
current coordinates are the first recorded throwing location, not a verified
exact pull-catching or pickup spot. These deliberately selected examples are
not field-matched league estimates. `reviewed_centering_counts.py` and its JSON
output retain every reviewed row, exclusions, source hashes and raw-event count
checks. Those charts remain a reviewed-sample demonstration, not a league
recalculation. No separate writing document is maintained; requested wording
is edited in this report.

On November 13, the league and team **scoring** views were recalculated to
follow the original seven receiving-point players. Completed possessions
before their first personnel change remain included. A possession crossing
that change, and later replacement-line possessions, are not assigned an
original-line goal or failure. Incomplete lineups and contradictory named
players are excluded; original possession numbers stay intact. The earlier
within-possession timeout exclusion is retained. A prior timeout alone does
not exclude a later possession when the recorded seven remain the same.
`original_line_scoring.py` and its JSON output preserve the row-by-row audit,
old-to-new count reconciliation, source hashes, refitted context models and
team scoring tables.

Also on November 13, **Huck attempt percentage: first versus second possession**
was added. It pools huck attempts over all physical throw attempts, including
centering passes, with completed and incomplete passes counted alike. Braden's
ShownSpace cutoff (>40 yards in distance and >30 yards forward) was confirmed
by Teddy in the research chat. The team selector includes all 22 teams; the
starting-location selector offers at least 60 yards from goal or all starts.
This comparison is first versus exactly second possession. It follows the
original seven, preserving attempts before a substitution even when a replacement
line finishes the possession. Same-seven timeout possessions and period-ending
attempts contribute to this throw-level rate; alternatives excluding them are
saved as checks. This differs from scoring's completed-possession denominator.
`huck_attempt_percentage.py` and its JSON output retain pooled counts, source
hashes, the lineup-audit reconciliation, per-game counts, and whole-game
bootstrap ranges. The existing team metric formerly called “Hucks as a share
of throws” now uses these updated 60-yard results and the name “Huck attempt
percentage.” Its original context model is not reused. Other league metrics
retain their earlier samples. The user's text edit “Huck completion %” on the
section 5 axis was preserved.

On November 9, the team tables gained exact-possession filters. Third means
`own_possession == 3`, excluding the 43 fourth-or-later possessions. The 204
third possessions retain their original numbering after timeout exclusions.
The filters use the existing metric eligibility rules; sample sizes differ
by measure. `possession_filters.py` and `possession_filters.json` preserve the
calculations and independent numerator/denominator checks. This addition
does not refit the original models or change the grouped league charts.
On November 10, the league early-huck comparison was parked in a closed review
section pending decisions about comparable starting locations and centering
passes. Its original bars remain available. A separate chart explains the
saved model estimates behind the +7.1 percentage-point comparison; no model
was refitted. Team early-huck figures are also marked as parked. A check using
all known starting locations shows why the whole-possession huck rate depends
on whether near-goal starts are included.
The possession review reconstructs selected examples from the
same export and raw event records, checked against ShownSpace's play-by-play.
Opening a preview does not query or refresh the database. The examples are selected
for interpretation and cannot establish a team or league tendency.
Teddy's reviews are recorded: A is setup, D is centering, and C and E are not
centering passes. Every actual throw remains counted.

The `html/` folder contains self-contained browser copies. They also open as
rendered reports in VS Code. These HTML copies are snapshots; edits to the TSX
update its VS Code preview, but require re-exporting to update the HTML copies.

To view or edit source: right-click the tab, then **Reopen Editor With → Text Editor**.
To return: **Reopen Editor With → UFA Research Preview**.

To change a sentence, open the `.canvas.tsx` file as **Text Editor**, press **⌘F**
and search for the sentence. Change the words between the `<Text>` and `</Text>`
tags, leaving the tags and expressions in curly braces intact, then save with
**⌘S**. Reopen with **UFA Research Preview** to see the result. The large `DATA`
line contains the reviewed numbers; ordinary wording changes do not require
editing it. The HTML copy is a separate exported snapshot and does not update
when you save the TSX file.

If using another computer, install the local `.vsix` package from
`research/vscode-preview/` through VS Code's **Extensions → … → Install from VSIX**.
Version 0.1.1 includes the possession review.

An earlier **New games · 12 clips** set contained eight opening
possessions and four later possessions across Austin–Vegas, Carolina–DC,
Minnesota–Pittsburgh and San Diego–Colorado. All twelve reviews are now saved,
bringing the archive to 52. Previous reviews remain in the review-set menu.
Use the
watch times to find the play on UFA.tv, answer **How does it start?** and
**Is there a completed centering pass?**, then choose **Save & next**. The main pass choices
are **No centering pass**, **Centering pass**, and **Cannot tell**. These display
labels preserve earlier selections and the working definition, including setup
transfers that do not move toward the middle. Team and
possession names replace internal case codes. Bar graphs remain below the
review area; definitions, provenance and eligibility notes remain in the
research files. **Export reviews** keeps a copy of all saved choices and notes.
UFA.tv playback stays in its own tab; the review page does not seek the video.
Windows were narrowed with broadcast spot checks; match the score and first
recorded pass before labeling. The selection and timing notes are in
`research/possession_review/next_review_batch_2026-11-12.json`. This purposeful
sample checks the working definition; it does not estimate league prevalence
or automatic-classifier accuracy. The two earlier obscured openings have
optional recorded-pass sequences, and their latest user confirmations are saved.

Open **Notes (optional)** to find **Dictate notes** beside **Notes or corrected
video time**. Open the browser copy in Chrome, pause the game audio, click the
button and allow microphone access if prompted. Recognized words append to the
current note. **Stop dictation** finishes the phrase; the text can then be edited.
Switching examples or exporting while dictation is running first stops it, so
the final words stay with the current possession. Notes use the same browser
saving and decisions export as typed notes. Dictation does not change a label or
the recorded video window. Speech processing depends on the browser and may be
online; this page saves text, not audio. Views without speech recognition retain
ordinary typing and device dictation. No Chrome extension is required.

Implementation references: [Chrome speech recognition](https://developer.chrome.com/blog/voice-driven-web-apps-introduction-to-the-web-speech-api/)
and the [Web Speech API specification](https://webaudio.github.io/web-speech-api/).
