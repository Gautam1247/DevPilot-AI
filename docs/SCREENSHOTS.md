# Screenshot capture checklist

## Current status

No authentic screenshots were found under `docs/` during the presentation review. No screenshots were generated, simulated or embedded. No video recording is included. The filenames below are **proposed capture names**, not links to existing assets.

Capture the running application with real project data. Store reviewed images under `docs/screenshots/` only after capture. Follow the [demo preparation](DEMO_GUIDE.md#prepare-before-presenting) and preserve the same browser session while collecting a run's evidence.

## Required views

- [ ] **Dashboard** — `01-dashboard.png`: show the actual dashboard and current session counts. Do not populate invented activity or metrics.
- [ ] **ZIP upload** — `02-zip-upload.png`: show a selected benchmark ZIP and **Analyze project**. Close the file picker before capture so personal directories are not visible.
- [ ] **Live Gemini analysis** — `03-live-gemini.png`: capture actual progress in live mode and pair it with the completed model-labeled result. Progress alone does not prove a successful Gemini response. Label mock captures explicitly if used instead.
- [ ] **Root-cause explanation** — `04-root-cause.png`: show the returned diagnosis and explanation for the actual run; do not replace the text with a prepared example.
- [ ] **Code diff** — `05-code-diff.png`: show **Proposed change**, its filename, and the real removed and added lines.
- [ ] **Baseline and candidate results** — `06-test-results.png`: expand **Test evidence & technical logs** to show the failing baseline and actual targeted/full outcomes. Use two images if necessary; preserve test names and statuses.
- [ ] **Technical logs** — `07-technical-logs.png`: show useful captured pytest evidence, with unrelated sensitive context excluded. Do not change failure messages or outcomes.
- [ ] **Patch approval and export** — `08-patch-export.png`: capture the approved state and **Download ZIP** for a verified candidate. Avoid browser download UI that exposes personal destinations.

## Publication checks

1. Review every image for API keys, authorization headers, capability tokens, `.env` contents, developer-tools network panels, personal directories, private source and desktop notifications. Do not publish sensitive captures. Prefer recapture; if redaction is necessary, visibly label it and do not obscure evidence needed to assess the result.
2. Keep labels honest: state the benchmark, live or mock proposal mode, and whether the image shows progress or a completed result. Do not label DevPilot's own verification as the separate independent evaluation.
3. Use readable framing and consistent dimensions. Cropping is acceptable; compositing different runs into an apparent single result is not. Review at the size the GitHub README will display.
4. Add descriptive alt text, captions and README image references **only after the corresponding real files exist**. Verify each relative path from the document that uses it. Do not embed upload/download URLs or capability-bearing links.
5. Record capture date, fixture name, proposal mode and any redaction here when assets are added. Stage only the reviewed images and documentation; generated project ZIPs and runtime workspaces remain local.

There are currently no screenshot assets to stage. The checklist does not imply that the views above have been captured.
