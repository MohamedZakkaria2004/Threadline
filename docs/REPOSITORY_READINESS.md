# Final repository readiness review

Date: 27 September 2026. **Ready to publish as a portfolio source repository: Yes.**
Overall prototype status remains **PASS WITH ISSUES** because the previously
documented host/performance limitations still apply. No Critical or High issue
remains in the checked publication scope. No repository was published and the
original Git index was not staged or committed by this review.

## What was checked and fixed

| Severity | Component | Reproduced problem and cause | Fix and verification |
|---|---|---|---|
| Medium | Publication privacy | `git ls-files --others --exclude-standard` included raw audit exports, host inventory and snapshot-path records. The ignore rules excluded only some artifact types. | Exclude generated artifacts, local environments, credentials, databases, vectors, backups and weights. Keep a tracked artifact guide and reviewed public summaries. Thirteen ignore probes pass; exact local generated passwords were compared against publication files without printing them. |
| Medium | Verification scripts | `phase2_live_evaluate` required health phase 2; `phase3_live_evaluate` required prompt v3. The finished application reports phase 3 and configured v4. These stale assertions would reject a healthy current server. | Accept phase 2 or later while requiring ready/model match; compare the prompt registry with the configured version. Fresh live health and registry checks pass. Entire historical multi-case runners were not repeated for this small assertion correction. |
| Medium | Windows setup | Removing uv from PATH on this host makes `py -3.12` fail even though uv's Python 3.12 is installed. Native command failures were checked only after the last setup command. | Fail immediately on environment/bootstrap/version errors; accept an explicit Python executable for the pip path. Fresh uv installation and fresh pip installation using the explicit interpreter both pass. Python 3.11 is rejected before creating an environment. The documented launcher prerequisite still applies when no interpreter is supplied. |
| Low | Fresh-checkout documentation | The README assumed this machine's existing models, indexed library and credentials location. Historical artifact links would become broken after excluding raw exports. | Document prerequisites, model installation, first-run seeding, exact printed credential path, restarts, configuration and test scope. Replace private artifact links with local provenance references and publish reviewed summaries. All relative publication links pass. |
| Low | Evidence portability | Git line-ending conversion can change the exact bytes of JSON/TXT evidence referenced by SHA-256 values. | Add attributes preserving the audit corpus and historical JSON evidence bytes. Verify both original NIST PDFs and all three historical summaries against the exact staged Git blobs in the disposable copy. |

## Fresh verification results

The rehearsal copied only Git-eligible files to a new directory outside the
workspace, created a new virtual environment, and staged that copy in a disposable
Git index. It used the already installed local Ollama models. This is a fresh
source/dependency/data rehearsal on the same Windows host, not a clean operating
system or newly downloaded model installation.

| Check | Result and scope |
|---|---|
| Python regression suite | **230 passed, 0 failed, 0 skipped**, 129.71 seconds. Includes 11 publication checks. Actual temporary SQLite/Qdrant; deterministic model double. |
| UI state regressions | **32 passed, 0 failed, 0 skipped**. JavaScript syntax checks also pass. |
| Fresh real-model HTTP smoke | **28/28 passed** in one completed final run. Separate store and server on port 8766. |
| Setup | Fresh uv/frozen-lock install and explicit-Python pip fallback both pass; all **34 pinned versions** match and dependency compatibility passes. |
| Dependency advisories | Completed OSV lookup returned **0 advisories** for those 34 versions at the recorded time. This is not proof of absence of vulnerabilities. |
| Publication boundary | Working files and the disposable Git index pass. Known local demo passwords are absent. No prior commits exist in the original repository; no historical secret purge is needed. |
| Source integrity | Official PDF hashes, historical evidence hashes and gold/source regression expectations pass. |
| Compilation/launch | Python compilation and PowerShell/JavaScript syntax checks pass. Original backend remains ready on source build `9ca7a344b04ced13`. |

The final live run seeded all 13 policies, authenticated all four accounts, checked
anonymous/CSRF and admin-view boundaries, served the local hero assets, answered a
policy question, created a real ticket, prevented duplicate replay, paused an
access request, denied self-approval, accepted an independent reviewer and created
only an access-review ticket. It refused email execution, restarted the isolated
backend and verified retained documents, workflows, conversation and login state.
No operational records were added to the normal demo library.

The actual RAG output was “Permanent employees receive 25 working days of annual
leave per calendar year.” Its quote is the identical sentence in the original
`annual_leave.md`, Paragraph 2. The persisted ticket description matches the
submitted monitor issue. Approval left the employee role unchanged. These were
checked against source text and saved records, not just HTTP success codes.

Fresh elapsed times were **14.70 seconds** for that RAG answer, **13.11 seconds**
for ticket planning, **10.39 seconds** for access-request planning and **0.11
seconds** for the deterministic unsupported-tool refusal. These few warm-host
measurements are not a performance guarantee or a new accuracy benchmark. The
historical 21-case public-corpus evaluation was not repeated in full; its results
and limitations remain separately labeled in the [engineering audit](E2E_AUDIT.md).

Two preliminary smoke attempts exposed mistakes in the private test harness:
it expected 403 where private conversations intentionally return 404, and it
attempted restart before the Windows launcher process tree/socket had released.
The harness was corrected to use the actual privacy contract and stop/wait for
only its owned process tree. The final complete run passed all 28 checks. Earlier
attempts remain private evidence; they were not relabeled as passing or counted
as application fixes. One existing test-client deprecation warning remains.

## Remaining boundaries and actions

- **Critical issues remaining:** none found in the executed scope.
- **Tests failed in the final runs:** zero. Automated checks do not establish
  universal security or semantic correctness.
- **Medium reliability concerns:** slow/resource-sensitive CPU inference and the
  earlier unexplained host interruption remain documented. Use a supervised
  local demonstration, adequate free RAM and sequential model evaluations.
- **Security/deployment:** demo identities and plaintext local storage are
  prototype boundaries. Keep the HTTP service on loopback. Independent human
  domain review and enterprise identity/deployment hardening are still required
  for a real pilot.
- **Optional repository improvements:** choose a project license if explicit
  reuse rights are intended; configure a private security-reporting channel and
  CI when the remote repository is created. No license was chosen on the owner's
  behalf. Third-party font notices and document provenance are included.
- **Exact remaining publication actions:** review the source file selection, run
  `python -m scripts.repository_check` again after staging, then commit and push
  when authorized. Do not force-add ignored raw evidence or runtime data.

**Ready for portfolio demonstration: Yes. Ready for the repository publication
step: Yes.** This review does not approve public hosting or production use.

See the [machine-readable summary](evidence/repository-checks-2026-09-27.json)
and the [security scope](../SECURITY.md).
