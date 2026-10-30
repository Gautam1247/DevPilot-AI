# Validation record

This file separates checks executed by the implementation agent from later results reported by the maintainer. Historical limitations below describe the environment at the time of each check.

## Maintainer-reported functional validation

Before repository preparation, the maintainer confirmed:

- 53 backend unit tests and 3 Docker integration tests passed.
- All three mock-AI benchmark workflows succeeded.
- Live Gemini generated and verified a discount fix and a fix for an unseen time-window consolidation bug.
- The frontend and backend run locally; browser analysis, approval and patched ZIP export work.

These are maintainer observations, not claims that the repository audit independently repeated the live Gemini calls, browser workflow or Docker benchmarks. No screenshots or raw private analysis artifacts are included as evidence.

## Historical implementation environment

The following historical sections predate the maintainer's successful live and Docker validation above. Current repository-audit results appear at the end of this document.

Environment: Windows PowerShell, Python 3.13.7, Node 24.12.0, npm 11.6.2, Docker CLI 29.2.0.

Docker Desktop's Linux engine was unavailable during implementation. The runner image and real container benchmarks could not be exercised. Three opt-in tests are provided to run once Docker is started.

No live Gemini requests were made. SDK imports, request configuration and error paths are checked without using an API key. The requested model identifier was checked against official documentation; account access is unverified.

## Executed checks — 2026-10-30

| Check | Actual result |
| --- | --- |
| Backend suite | **53 passed, 3 skipped**; skipped tests are the opt-in Docker benchmarks |
| Backend import and Gemini SDK configuration | Passed; `HttpOptions(timeout=30000, retry_options=HttpRetryOptions(attempts=1))` accepted |
| Frontend TypeScript check and Vite production build | Passed; Vite 6.4.5; main JS bundle 255.96 KB / 78.79 KB gzip |
| Live Uvicorn startup and `/api/health` | Passed; HTTP 200, mock AI enabled, Docker unavailable |
| Live Vite document and `/api/health` proxy | Passed; both HTTP 200 |
| Live ZIP upload and analysis request | HTTP 201 and 202; terminal `INCONCLUSIVE` with the expected Docker-unavailable message |
| Mocked full API workflow | Passed: upload, baseline evidence, mock proposal, target/full evidence, approval, ZIP contents, rejection and blocked download |
| Source checks | No Gemini-style key, frontend secret variable or localStorage token use found; subprocess use confined to Docker adapter |

The suite includes malicious archive names, symlinks, collisions, compression ratio and size/count limits; patch and schema restrictions; original preservation; failed/partial/regressed/inconclusive outcomes; capability expiry; origin and host checks; rate limiting; candidate integrity; missing Docker/key and Gemini error handling.

One dependency deprecation warning remains: this installed Starlette release warns that its httpx-based TestClient adapter is deprecated in favor of httpx2. All tests pass. No additional HTTP client was installed solely to suppress this warning.

Mocked adapter tests establish application behavior only, not real Docker benchmark success. No browser automation or screenshots were available; responsive styling and interaction behavior have not been visually exercised. Live Gemini account/model access, image build, container isolation at runtime, and all three real benchmark outcomes remain unverified.

Temporary Uvicorn and Vite processes used for smoke checks were stopped after validation. No infrastructure was deployed.

## Repository preparation checks — 2026-10-30

- Backend: **77 passed, 3 skipped**, using the existing virtual environment and a unique project-local `--basetemp`. Docker integration tests were explicitly disabled for this audit. One pre-existing Starlette TestClient deprecation warning remains.
- The first audit test invocation encountered fixture setup errors because the parent `.pytest_tmp` directory was missing. Creating that directory and repeating validation resolved the issue; application behavior was not changed. README commands now create the parent explicitly.
- Frontend: `npm.cmd run build` passed both TypeScript validation and the Vite production build. No UI styling or application code changed during this audit.
- Docker: the Dockerfile, fixed runner and documented `docker build -t devpilot-runner:local ./sandbox` command were inspected. No image rebuild or real container benchmark was run during this audit.
- Repository candidates: 45 text files reviewed; no actual credentials, private environment values, personal home paths, unexpected binaries or oversized files detected by the local pattern/exact-value checks. Synthetic test credentials were identified separately. No standalone secret scanner was installed; these checks are not a guarantee that every possible secret format can be detected.
- `.env` variants, credential files, dependencies, caches, runtime workspaces, local uploads, build output and generated patched ZIP names are excluded. `.env.example` contains every configuration name read by the backend and an empty API-key placeholder. Source benchmarks remain included.
- No live Gemini requests, browser workflow or external link checks were repeated. No screenshot assets were available. Working `.env`, runtime projects and user files were preserved.

The security model remains a local MVP: pytest evidence is not tamper-proof, and Docker restrictions do not establish safety for public multi-tenant execution. Publication of the source does not change those limitations.
