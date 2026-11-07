# UFA research reports

Open any of the `.canvas.tsx` files in this folder in VS Code. They open
directly as rendered reports through the local **UFA Research Preview** extension.

- `UFA-dead-disc-first-pass.canvas.tsx` — throws after recorded stoppages.
- `UFA-pull-centering.canvas.tsx` — each team's most frequent centering recipient.
- `UFA-oline-regain-hucking.canvas.tsx` — first, second, and later O-line possessions: throw counts, huck timing, catches, scoring, and breaks after turnovers. The team view defaults to the 12 playoff teams and can show all 22.
- `UFA-possession-review.canvas.tsx` — five recorded possessions, with a field view and throw-by-throw controls for discussion.

Dropdowns, tables, charts and expandable methods work without a server or terminal.
The dead-disc and pull-centering reports retain their earlier research snapshots.
The O-line report was expanded on November 5–6, 2026 using the preserved data;
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
