# UFA research reports

Open any of the `.canvas.tsx` files in this folder in VS Code. They open
directly as rendered reports through the local **UFA Research Preview** extension.

- `UFA-dead-disc-first-pass.canvas.tsx` — throws after recorded stoppages.
- `UFA-pull-centering.canvas.tsx` — each team's most frequent centering recipient.
- `UFA-oline-regain-hucking.canvas.tsx` — **O-line offense after turnovers**: throw counts, huck timing, catches, scoring, and breaks after turnovers. The team view defaults to the 12 playoff teams and can show all 22. **Possession shown in tables** selects first, second, or exact third possessions in both team tables. The comparison option retains the original first / second / third-or-later view.
- `UFA-possession-review.canvas.tsx` — film-review queue with saved labels, optional notes, game links and review-progress charts.

Dropdowns, tables, charts and expandable methods work without a server or terminal.
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
checks. The older league figures remain unchanged. No separate writing
document is maintained; requested wording is edited in this report.
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

The film-review page opens with **New games · 12 clips**: eight opening
possessions and four later possessions across Austin–Vegas, Carolina–DC,
Minnesota–Pittsburgh and San Diego–Colorado. All twelve reviews are now saved,
bringing the archive to 52. Previous reviews remain in the review-set menu.
Use the
watch times to find the play on UFA.tv, answer **How does it start?** and
**How is the first pass used?**, then choose **Save & next**. The main pass choices
are **Immediate attack**, **Centering pass**, and **Cannot tell**. These display
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
