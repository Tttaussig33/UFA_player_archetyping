# UFA Research Preview

Opens UFA research reports directly as interactive reports in VS Code:

- UFA-dead-disc-first-pass.canvas.tsx
- UFA-pull-centering.canvas.tsx
- UFA-oline-regain-hucking.canvas.tsx
- UFA-possession-review.canvas.tsx

The portable `.ufa.html` exports open in the same preview and also work in a browser.
All data stays inside the report. There is no server, terminal launcher or network request.
Dropdowns, charts, tables and expandable methods are preserved.

To edit the TSX source, right-click the editor tab and choose **Reopen Editor With → Text Editor**.
After saving, switch back to **UFA Research Preview**. Changes made in another editor update an open preview automatically.

This local extension supports the display components used by these reports;
it is not a general React or Cursor canvas renderer. Original research source and
data are not modified by the preview. The extension uses a restricted webview and
does not expose commands or filesystem access to report scripts.

The bundled TypeScript compiler is licensed under Apache License 2.0; see vendor/TypeScript-LICENSE.txt.
