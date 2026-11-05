# UFA research reports

Open any of the `.canvas.tsx` files in this folder in VS Code. They open
directly as rendered reports through the local **UFA Research Preview** extension.

- `UFA-dead-disc-first-pass.canvas.tsx` — throws after recorded stoppages.
- `UFA-pull-centering.canvas.tsx` — each team's most frequent centering recipient.
- `UFA-oline-regain-hucking.canvas.tsx` — first, second, and later O-line possessions: throw counts, huck timing, catches, scoring, and all 22 teams.
- `UFA-possession-review.canvas.tsx` — five recorded possessions, with a field view and throw-by-throw controls for discussion.

Dropdowns, tables, charts and expandable methods work without a server or terminal.
The dead-disc and pull-centering reports retain their earlier research snapshots.
The O-line report was expanded on November 5, 2026 using the preserved data;
its calculation and validation files are in `research/oline_possessions/`.
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

If using another computer, install the local `.vsix` package from
`research/vscode-preview/` through VS Code's **Extensions → … → Install from VSIX**.
Version 0.1.1 includes the possession review.
