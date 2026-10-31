# Validation record

This record distinguishes automated checks executed during earlier implementation/audit work from subsequent results reported by the maintainer. The presentation update is documentation-only: it does not rerun application tests, call Gemini, or establish a new live success.

## Current evidence summary

| Check | Actual result | Evidence source and boundary |
| --- | --- | --- |
| Final security-audit backend suite | **109 passed, 0 failed, 3 skipped** | Recorded in [SECURITY_AUDIT.md](SECURITY_AUDIT.md#verification), dated 2026-10-31. The skipped tests were the three opt-in Docker integrations. Mocked SDK and Docker tests establish application behavior, not external service success. |
| Subsequent Docker regression | **3 integration tests passed** | Confirmed by the maintainer after the audit. Not rerun during this documentation pass. The test implementation explicitly enables mock AI and asserts both `VERIFIED` and full-suite success. |
| Three original debugging benchmarks | Discount, off-by-one and sorting verified | Maintainer-confirmed actual Docker execution with **mock-generated** patches. These are the same three cases exercised by the Docker integration suite, not three additional independent benchmarks. |
| Live Gemini discount demonstration | Genuine Gemini-generated fix verified | Maintainer-confirmed live application result; separate from the mock discount integration test. No raw response or recording is bundled here. |
| Unseen time-window consolidation bug | Fixed with live Gemini and independently evaluated | Maintainer-reported outcome. The original unseen fixture, detailed independent evaluation output and test count are not bundled in this checkout. The three original fixtures remain the only included benchmarks. |
| Browser review and export | Approval and patched ZIP download exercised | Previously confirmed by the maintainer. No browser automation results, screenshots or recording are supplied by this presentation update. |

These observations are **not a statistical success rate over a representative dataset**. Backend test counts, benchmark cases and live demonstrations measure different things and must not be added together as a debugging success metric. No latency, throughput, production adoption or broad correctness claim is established.

## Included benchmark cases

| Source fixture | Intentional defect | Proposal mode in Docker integration |
| --- | --- | --- |
| [Discount](../benchmarks/discount_bug/pricing.py) | Percentage is used without dividing by 100 | Deterministic mock |
| [Off-by-one](../benchmarks/off_by_one_bug/sequence.py) | Inclusive range endpoint is excluded | Deterministic mock |
| [Sorting](../benchmarks/sorting_bug/ordering.py) | Ascending operation sorts in reverse | Deterministic mock |

The [Docker integration test](../backend/tests/test_docker_integration.py) runs each original baseline and patched candidate through the real runner. It requires `VERIFIED` and `full_suite_success`. The [engine](../backend/app/engine.py) defines verification through test evidence, never model confidence. A separate live Gemini proposal for the discount case does not change the mock provenance of the automated benchmark.

## Historical checks

| Stage | Recorded result |
| --- | --- |
| Initial implementation, 2026-10-30 | 53 backend tests passed, 3 Docker tests skipped in the agent's environment; frontend TypeScript/Vite build passed. A Docker-unavailable API smoke run correctly ended inconclusive. |
| Later functional confirmation | Maintainer reported 53 unit tests and 3 Docker integrations passing, all original benchmark workflows, live discount and unseen fixes, and browser approval/export. |
| Repository preparation, 2026-10-30 | 77 backend tests passed, 3 Docker tests skipped; frontend build passed. The first audit invocation needed the project-local pytest temporary-directory parent created before validation could complete. |
| Targeted security audit, 2026-10-31 | Controlled reproductions preceded fixes; focused sets of 59 and 57 tests overlap and must not be summed. Final suite: 109 passed, 3 skipped. |
| After the security audit | Maintainer confirmed all 3 Docker integration tests passed on rerun. This resolves the outstanding benchmark rerun; it does not resolve the audit's remaining design limitations. |

Docker Desktop's Linux engine was unavailable during the agent's security audit. That statement in the audit is historical; it does not contradict the subsequent maintainer-confirmed Docker run. One existing Starlette/httpx TestClient deprecation warning was recorded in the backend suite. No dependency was installed merely to suppress it.

Earlier local secret scans checked patterns and private environment values without displaying credentials. Such checks are not a comprehensive secret-detection guarantee. No screenshot assets existed at presentation review; [SCREENSHOTS.md](SCREENSHOTS.md) records the capture checklist.

## Presentation documentation checks — 2026-10-31

- Checked six Markdown documents, local link targets and heading anchors, table and code-fence structure, and the two Mermaid diagrams against the simple flowchart syntax used here. External URLs were checked for syntax only; GitHub rendering was not previewed.
- Parsed all eight README PowerShell command blocks without executing installation, test, build or analysis commands. Referenced prerequisites, npm script names and documented environment variable names match the checkout.
- Confirmed the showcase descriptions contain 50 and 124 words, respectively, and the screenshot checklist covers eight required views. No screenshot image links or assets were added.
- Local credential-pattern and private-environment-value comparisons found no sensitive credentials in the reviewed Markdown. Secret values were not displayed. These checks are not exhaustive secret detection.
- Confirmed changes are limited to the README and four documentation files. No application code, dependencies, benchmark fixtures, Docker settings or frontend styling changed. No application tests, browser recording or paid API calls were performed in this pass.

## Reproduce checks deliberately

Use the [README test commands](../README.md#tests-and-build) for the mocked backend suite and the three opt-in Docker integrations. These commands do not call Gemini. Start Docker Desktop and build the fixed runner before enabling Docker tests; uploaded code must not be executed by host pytest.

For a new live demonstration, follow [DEMO_GUIDE.md](DEMO_GUIDE.md). Live mode can incur API cost and requires explicit configuration. A later run may fail because of model output, account access, quota or infrastructure; earlier successes do not guarantee a new result. Keep the actual baseline, patch and candidate outcomes together, and distinguish application verification from any independent evaluation.

The application remains a local MVP. Pytest evidence is not tamper-proof, Docker restrictions do not certify safe public multi-tenant execution, and test success only covers observed behavior. See the [security audit](SECURITY_AUDIT.md) for applied corrections and deferred findings.
