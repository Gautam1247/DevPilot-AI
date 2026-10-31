# DevPilot AI — targeted security and reliability audit

**Date:** 2026-10-31 (Asia/Calcutta). **Scope:** local MVP; Docker execution, API capabilities, Gemini integration, pytest evidence, ZIP uploads, patch/approval/export integrity and React rendering. No deployment, new dependencies, live Gemini requests, destructive payloads or host-escape attempts.

## Boundaries and method

Source inspection, controlled in-memory API/SDK/subprocess tests, exact-byte export checks, and credential-pattern/private-value scans were used. Uploaded Python was never executed on the host. Docker Desktop's Linux engine was unavailable: `docker info` and image inspection failed because its named pipe was absent. Runtime isolation and the three real Docker benchmarks could not be independently rechecked in this audit; previously reported successful runs are recorded in [VALIDATION.md](VALIDATION.md).

The API host and its user account remain trusted. Uploaded projects and model output are untrusted. Docker constrains project execution, but the pytest interpreter is shared with the code being tested. Capability tokens protect project access; they are not multi-user authentication. Filesystem-integrity findings below require a local writer or storage corruption, not an unauthenticated remote file-write capability.

## Findings and remediation

No CRITICAL issue was confirmed in this scope. HIGH ratings below concern the accuracy of verification/export claims, with their prerequisites stated explicitly.

| ID / severity | Affected location | Evidence and disposition |
| --- | --- | --- |
| H1 — HIGH | `backend/app/runner.py`, `DockerRunner.run` / new `parse_report` | The old `rpartition` parser accepted a trailing passing report after an earlier failure report when the observed exit was 0. A controlled mocked process reproduced acceptance. **Mitigated:** require exactly one line-framed final report; reject duplicate JSON keys, trailing output and inconsistent evidence. This closes ambiguous framing, not all evidence forgery; see H4. |
| H2 — HIGH, requires storage mutation | `backend/app/workspaces.py`, `tree_hash` | Two distinct trees produced an identical digest: merging a later filename, NUL delimiter and content into the previous file reproduced the same input bytes. This was ambiguous encoding, not a SHA-256 collision. The tampered fixture is not a valid upload. **Fixed:** length-prefix each path and content field; reject detected filesystem links when reading snapshots. |
| H3 — HIGH, requires concurrent storage mutation | `backend/app/main.py`, `download` | A controlled writer changed a candidate after its hash check; the old endpoint returned HTTP 200 with the altered bytes. **Fixed:** validate an in-memory file snapshot, then construct the ZIP from those same bytes. Approval and download use the same integrity helper; detected missing/changed/linked candidates return sanitized HTTP 409. |
| H4 — HIGH residual design limitation | `sandbox/runner.py`, `Evidence` and `pytest.main`; backend report parser | Project code and the evidence plugin share an interpreter and stdout. A single well-formed, internally consistent fabricated report cannot be distinguished from genuine evidence by this protocol. Code can also manipulate pytest hooks or outcomes in-process. `--noconftest` and plugin-autoload controls do not isolate pytest from the test code. **Documented, not solved:** independent trusted supervision and a stronger evidence boundary require design work. |
| M1 — MEDIUM, deferred | `backend/app/security.py`, `extract_zip`; `backend/app/main.py`, `upload` | A deliberately corrupted DEFLATE stream raises a decompressor exception outside the handled exception set. A controlled API probe returned sanitized HTTP 500 and retained one project record. Repeated malformed uploads can consume the session's 40-project allowance, subject to the existing rate limit. Future fix: map decompressor failures to a safe validation error and reliably release failed upload records/workspaces. No application change was made for this medium finding. |
| M2 — MEDIUM, deferred | `backend/app/runner.py`, cleanup in `DockerRunner.run` | The code attempts `docker rm -f` after execution/timeout but ignores cleanup failure. A stopped/unresponsive daemon can therefore leave cleanup unconfirmed. Unit tests confirm the cleanup attempt, not daemon enforcement. Future work: distinguish expected already-removed containers from cleanup failures and record actionable cleanup status. |
| L1 — LOW, defense in depth applied with H1 | `backend/app/engine.py`, `verification`; `backend/app/schemas.py`, `TestRun` | Direct comparator fixtures could be marked VERIFIED despite contradictory exit status or duplicate collected IDs. The normal Docker adapter already checked these cases, so this was not a separate reachable adapter bypass. The new shared `has_complete_evidence` predicate now checks both producer and comparator boundaries. |
| L2 — LOW, deferred | `frontend/src/api.ts`, `request`; `frontend/src/App.tsx`, polling | Fetch has no explicit client deadline. A hung request can leave an operation busy or suspend polling progress. No false success was observed: status remains backend-driven and errors stop polling. Consider AbortController and a bounded request timeout later. |

### Compatibility

No public route or response schema changed. A normal fixed-runner report remains accepted. Duplicate/non-final reports now yield INCONCLUSIVE, including otherwise harmless output printed after the report footer. Candidate digests are internal and now use an unambiguous encoding. Restart the backend before using these changes; existing browser sessions already lose access on restart in this MVP. Export content is checked byte-for-byte, but ZIP metadata such as timestamps is not preserved by the snapshot export. No sandbox image changes or rebuild are needed for these host-side fixes.

## Control review

| Area | Evidence / result |
| --- | --- |
| Docker command | Fixed argument list; no shell, model commands or host execution of uploaded modules. UID 10001, network none, all capabilities dropped, no-new-privileges, 1 CPU, 256 MB memory and swap limit, 64 PIDs, read-only root and sole project bind mount, 64 MB noexec/nosuid tmpfs, no Docker socket/secret mounts. Fixed image and invocation; no uploaded dependency installation. Command construction and timeout/output-limit cleanup tested; actual runtime flags not inspected because Docker was stopped. |
| API authorization | Secure random project IDs and 32-byte capability tokens; only token hashes retained server-side; constant-time comparison and expiry checks. Missing, incorrect, cross-project and expired capabilities rejected on results, analyze, approve and download. Approval state and VERIFIED status gate download. Exact origin/host allowlists, explicit GET/POST CORS policy, body limits and upload/analysis rate limits remain in place. |
| Gemini | Backend-only key configuration; explicit Developer API endpoint; one attempt, 15-second network-operation timeout and 40-second cancellable request deadline. Structured output is strictly Pydantic-validated before path/AST/import/patch checks. Mocked SDK tests cover request shape, cancellation and sanitized HTTP/network errors. No live API call or key modification occurred. |
| Test comparison | Complete nonempty collection, unique IDs, matching result keys and process-status consistency required. The target must fail before and pass in targeted and full candidate runs; collection must remain unchanged, passing tests cannot fail or skip, and no new failure is accepted. Full-suite success remains distinct from partial improvement. These are consistency checks, not adversarial attestation. |
| ZIP validation | Existing traversal, absolute/Windows path, symlink/special-file, duplicate/case collision, file-size/count and compression-ratio defenses tested. Added encrypted-entry and embedded-NUL filename negatives. The malformed-DEFLATE exception gap is M1. Extraction is into a newly generated workspace, not a user-selected destination. |
| Patch/export | Only an existing allowed non-test Python file can change; exact unique replacement, AST and dependency/dynamic-execution checks remain. Original preservation, failed/unapproved/rejected export denial, post-approval tampering and checked-snapshot export tested. AST rules are conservative checks, not a semantic proof of safe Python. |
| Frontend | Source review found text rendering for logs/diffs, no unsafe HTML insertion, no frontend API key or sensitive VITE variable, and no local/sessionStorage token persistence. Capability values remain in React memory. No frontend files changed; build/browser tests were not rerun. |
| Secrets | Pattern and exact private-environment-value comparison found no credentials in 48 tracked/existing bundle files or 45 existing historical blobs. Values were not displayed. `.env` is ignored; staged changes receive a separate precommit scan. These local checks are not an exhaustive secret detector. |

## Verification

| Stage | Executed result |
| --- | --- |
| Controlled pre-fix reproductions | 5 failed, 1 passed, 0 skipped — demonstrated framing, digest, export and comparator issues |
| Focused tests after corrections | 59 passed, 0 failed, 0 skipped |
| Expanded evidence/API/ZIP negatives | 57 passed, 0 failed, 0 skipped; overlaps the preceding focused set |
| Final backend suite | **109 passed, 0 failed, 3 skipped** |

All pytest runs used unique project-local temporary directories. Final command shape, from `backend/`: `$env:RUN_DOCKER_TESTS='0'; .venv/Scripts/python.exe -m pytest tests -q --tb=short --basetemp=<unique .pytest_tmp child>`. One existing Starlette/httpx TestClient deprecation warning remains. Mock debugging, the official SDK adapter with mocked transport, human approval, rejection and ZIP contents are covered by the passing suite.

The skipped tests are exactly the three opt-in Docker benchmark integrations. Neither a runtime sandbox inspection nor a fresh real benchmark success is claimed. No frontend build was needed because frontend files were unchanged. No live Gemini request, infrastructure deployment, remote/history change or Git push was performed.

## Remaining limits and next steps

Start Docker Desktop and rerun `tests/test_docker_integration.py` with `RUN_DOCKER_TESTS=1` using the README's project-local temporary-directory commands. No live Gemini request is necessary for that check. Prioritize M1's failed-upload cleanup next.

Before any public service: isolate evidence supervision from project code, use stronger execution isolation and pinned images, add real authentication/authorization and durable job/quota controls, handle cleanup failures explicitly, and review uploaded-secret handling. This audit does **not** certify the application as production-hardened or safe for public multi-tenant execution. Compromise of the host account, active filesystem races while reading paths, malicious test behavior and container/host vulnerabilities remain outside the guarantees established here.
