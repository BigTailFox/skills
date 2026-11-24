---
status: done
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Prepare, run, score and summarize paired historical replays with verified inputs, isolated slice tests and blinded judgments.
refs: [D012]
based_on: [D012@r1]
reviewed: 1
reviewers: [gpt-6.2-astra, gemini-4-neon-xhigh]
approved: 1
---

# P011: Paired workflow replay

Implements [D012: Paired replay of Canon workflows](../../designs/D012-workflow-replay.md).

## Current state

All five slices are done. The three code reviewers finished confirmation and targeted rechecks. The public CLI and the historical acceptance case passed final verification.

## Slices

### S1: Prepare a historical case that survives loss of the source checkout

Status: done

Risk: The retained first-round tree can differ from the opening snapshot. Restoring a whole source repository would also expose later history.

Implement `prepare` in `scripts/replay_workflows.py` with local helpers under `scripts/`. Consume the existing offline report and its Q9, case and evidence records. Support all documented selectors and evidence options. Pin the immutable case input and both suites in a private case directory and publish its versioned receipt only after successful verification. Reuse Git/trace parsing for the exact store, unit, revisions, scoped diff and untracked files, verified as-built tree, canonical suite digests, project installs and fixtures. Preserve the original archive's neutral requirement when available. Read the real slice span, criteria mapping, role evidence and case-level findings for later dispatch and adjudication. Leave unknown and conflicting evidence explicit. Use bound host records only for the specific dispatch/role being recovered.

At the public `prepare` seam, drive real temporary Git and trace stores. Check a full-document gate, document/prepared/live diffs, a verified as-built input and a slice. Compare the live patch to independent Git output with a staged addition, a deletion whose path remains on disk and an executable untracked file. Check an identical-suite control and a distinct candidate (including a flat historical layout), fixture modes and the saved input after the source checkout moves. Reject an excluded/ambiguous case, missing object, unsafe fixture overlap or escaping path and stale criteria mapping before dispatch. Check incomplete neutral scope, absent role effort and uncorroborated groups without inventing values. Repeating an identical preparation preserves its receipt. A conflicting preparation cannot overwrite an existing case.

Recover the verified scope's actual paths and flags through the existing `code_scope` / `gate_scope`, `Archive` and `Trees` logic. The public report intentionally emits hashes for some of these fields. Use bound Codex session intervals for per-role identity and effort. For a slice, distinguish “no uniquely attributed review” from “unique review with unknown findings”. Join the latter review's first-round sources to its own corroborated groups and preserve the unknowns. Exercise both cases. Freeze the initial contained launch's brief, source identity and digest privately at preparation, or its unavailable status. Test missing, outside and ambiguous launches and a later resume/replacement. Remove the test host profile before running.

For a code review, pin the plan's named slice requirements and tests, or all its slices for a whole-plan change. For a plan-less review use the unambiguous archived `Requested delivery`. Test both plan variants, the archived line, conflicting sources, and null delivery on gates/slices. The receipt carries text, source and digest when known. Without a criteria file retain the entire frozen slice as one null-argv criterion. With a mapping, preserve uncovered nonblank body paragraphs as unavailable, excluding the heading and structural Status/Risk lines. Reject duplicate IDs, empty argv and line ranges outside that slice. Exercise a shallow candidate history and SHA-256 source repository where supported. Reject a mixed or unknown unit manifest even if individual suite files are available.

### S2: Run a paired review with the operator's versioned runner

Status: done

Risk: A controller restart or concurrent invocation can dispatch the same paid slot twice or credit the wrong suite, role or input.

Implement `run` for reviews on the prepared case. Pin and validate the executable/config, resolve per-role settings and effective tool paths, preflight grants, materialize independent workspaces and install each suite before dispatch. Send the D012 v1 request to the trusted machine-local executable and verify its result and confined evidence bytes. Preserve a private, durable attempt journal, opaque IDs, order, outcomes, partial evidence, wall time and per-role token components. Serialize slot claims and have a supervisor owned by the case persist the runner's terminal result even if the invoking CLI exits. Seal each review's first-round reports and publish the neutral packet and template. Build claims from verbatim first-round reports. Include the historical inventory independently of the new claim count. Rebuilding an unchanged packet must preserve its bytes.

At the public `run` seam, a deterministic **local executable** observes both suite versions over three alternating pairs, the neutral delivery and distinct workspaces. A self-hosted Canon fixture catches a tool path resolving to the wrong version. Wrong model/effort, wrong attempt ID, corrupt evidence, a post-boundary call or insufficient granted inputs cannot yield a comparable result. Exercise two concurrent controllers and a terminated controller on a real subprocess. Reattach to a known live job, preserve uncertain dispatches, and retry a verified terminal interruption with a fresh ID. Check that completed slots are counted once and changed runner or config bytes cannot resume the run. Inspect the blinded packet for zero-claim attempts, duplicate sources and removal of arm/model labels, raw host material and private paths.

Check the target and patch again after fixtures and project installs, including Codex/Cursor paths, Claude links, excludes, exact tracked reuse and tracked collisions. Before crediting an attempt, check every reported `loaded` path and SHA-1 Git blob against that role's assigned suite, including an observed mismatch despite a successful preflight. Exercise missing/conflicting model, manual reviewer, ungranted destination, a different resolved runner path and fewer than three repetitions. A dead supervisor without a terminal record leaves the slot uncertain even if its lock is free. The supervisor holds an exclusive dispatch lock and publishes an atomic terminal record, including observed runner termination. Test teardown reaps launched fixture processes.

Bind claim text and severity to the line ranges returned by the first-round heading parser. Preserve report validity through sealing. Against a known historical defect, a well-formed, completed no-findings report yields an empty claim list; a blank, truncated or malformed report makes recall unknown. Publish blinded rows and referenced files in stable order by random opaque identifiers independent of arm, time, slot and dispatch. Reversing private journal order with fixed IDs and evidence yields identical packet bytes.

### S3: Evaluate slice artifacts and pinned tests without exposing the controller

Status: done

Risk: Worker output and commands can change their checkout. The private receipt, arm mapping and the other arm must remain inaccessible to them.

Extend the same `run` and packet interfaces to slices. Preserve terminal `done`, `blocked` and `stuck` as completed worker observations and distinguish host stops. Validate and import the sole parentless result ref from the self-contained Git bundle v3 into a fresh repository with the correct object format. Freeze the final tree, use a clean tree and fixtures for each pinned criterion, and execute argv in an enforced local sandbox with only the explicitly granted test tools and runtime. On Linux, probe Bubblewrap with an empty root, private process/network namespaces, only the disposable tree writable, and individually granted test executables and runtime inputs mounted read-only. Distinguish sandbox startup failure from an actual nonzero test exit. Report unavailable on an unsupported host or when that boundary or a prerequisite cannot be provided. Capture status and digests outside the child. Implement the private comparison against the initial contained historical worker brief and expose only its status and digests. Blind the artifact and test evidence, including opaque references for later-review matching.

At `run`, verify a bundle containing executable, symlink and deleted files, reject a bad ref, history or prerequisite, and test all three worker statuses plus a host stop. A test that writes in its copy cannot modify the next test, saved artifact or host fixture. Test access confinement on a capable host and the unavailable path without isolation. Exercise pass, fail, no command and missing dependency. A later repair of the live project cannot change a sealed result. Verify that the first worker's brief is selected unambiguously and neither the brief nor execution cost enters the blinded packet.

Use the selected runner profile's optional nonsecret isolation setting `settings.test_runtime_files`, an array of `{fixture, target}`. Each source is a regular file named in the prepared, sealed fixture inventory. Each target is a normalized absolute file path in the otherwise empty sandbox, disjoint from the work tree, reserved system mounts and other grants. This setting can map already-granted bytes into the runtime layout. It grants no new host paths. Keep `test_tools` for separately granted executable entry points. Demonstrate an actual dynamically linked criterion with its loader and libraries and an unavailable result when a required file is missing. Reject a host directory, private case path, escaping fixture or overlapping target before executing the criterion.

Check the bundle object format, tree paths and modes before checkout. Exclude fixture paths, the actual injected skill paths and Git metadata. Revalidate each destination and all ancestors in the final tree before restoring clean fixtures, refusing symlinks and conflicting worker-created files. Export blinded artifact views from Git objects without following links. Test an object-format mismatch and a replaced parent directory with an outside sentinel. Invalid/missing artifacts leave the worker status measurable. Compare the new brief to the evidence S1 pinned after removing the historical host profile. Verify a changed instruction and each unavailable result without exposing either brief.

### S4: Score one blinded case reproducibly

Status: done

Risk: A missed historical defect, duplicate novel claim or unresolved match can change a denominator without changing the apparent rate.

Implement `score` on the sealed case, blinded packet and optional judgments from D012. Validate version, packet/evidence digests, opaque attempt and claim membership, scope and verdict enums, historical references and later-review attribution. Retain partial or unknown judgments at their affected comparisons. Produce `result.json` with case/receipt identities, role-specific costs, counts and denominators, worker indicators, known metrics, uncertainties and comparable pair differences. Keep the original source, runner and test process outside scoring.

At `score`, a worked review fixture with two historical sources for one defect, an empty report, two reports of one valid novel defect, a declined claim and an out-of-scope request yields the exact expected counts and recall. An unknown inventory, duplicate membership, stale packet or modified evidence cannot produce a misleading full rate. On slices, compare only common decided criteria and later groups. Keep blocked versus stopped distinct, measured parent/child components separate, and missing measurements unknown. Score a slice with no attributable later groups without a judgments file. Two identical invocations after the original project and runner are unavailable produce byte-identical results.

Test the valid zero-claim report at 0/1 and the truncated report at unknown recall. With absent or contradictory delivery, score a diff-decidable contract and keep a scope-dependent request unknown. Provisional history withholds unproven novelty. Zero denominators produce no rate. Negative or inconsistent token components (including cached input above input or reasoning output above output) are unknown. Check the required judgments for reviews and for slices with attributable later groups. Verify steering, brief status/digests, cohort keys, sparse-pair flag and separate boundary costs in the result, and verify that the private receipt, raw host data and brief text are absent.

### S5: Summarize independent cases and verify the complete operator workflow

Status: done

Risk: Duplicate case directories and unequal numbers of completed repetitions can implicitly weight one historical case several times.

Implement `summarize` over verified case results. First calculate per-case means over comparable pair differences, then equal-weight independent cases in each compatible cohort, with project-level rows before any cross-project combination. Keep conflicts, partial pairs, sparse cohorts and unavailable metrics visible. Document a runnable local example adjacent to the offline report in the root README, covering the external runner protocol, input grants, optional test runtime and the handoff between blinded judgments and scoring.

At the `summarize` CLI, use cases with unequal pair counts and known metric values to distinguish equal-case weighting from pooled attempts. Check duplicate copies, conflicting judgments/inputs, incompatible hosts/configs/suite pairs, independent case counts and per-metric pair counts. Exercise `prepare → run → score → summarize` with an A/A control and an A/B fixture using the offline executable. Also prepare at least one actual eligible Canon trace and drive an offline runner on a compatible real case, reporting the verified inputs and limits separately from synthetic test outcomes. Run the repository validation with measured text budgets and its existing discovery check.

Check each cohort dimension (project, kind, tier, host, role settings, runner config and suite pair), per-project and compatible combined rows, observed counts/denominators and wall/token measurements. Distinct suite pairs for one historical case are separate comparisons. Reject stale results against their sealed evidence. Keep the real-trace check in local acceptance, outside the portable test suite. This checkout has the eligible D003@r9 gate `20261113T130221Z-45876c`; candidate `8478e130d51b58bf4549f406e35ec5629118134b` changes the review skill while retaining the project's prescribed `canon.py`. Its historical sources are provisional. Record the outcome in the Log.

## Notes

- The four public operations and the v1 wire formats come from [D012§interface: replay commands](../../designs/D012-workflow-replay.md#interface), [D012§runner-protocol: runner protocol](../../designs/D012-workflow-replay.md#runner-protocol) and [D012§blinded-scoring: adjudication](../../designs/D012-workflow-replay.md#blinded-scoring). The operator supplies the machine-local executable and nonsecret configuration. The tests supply a deterministic runner at that same boundary.
- Keep both the prepared input and run state local. Publish receipts, reports, packets and results atomically. A workspace gets only its selected synthetic objects, tools and fixtures. Never expose alternates or the original Git history. Preserve the project's source object format for input trees and D012's canonical SHA-1 for comparable installation identity.
- Use the existing trace readers, Git primitives and first-round report grammar. Project-local `scripts/` and `tests/` carry replay code and public CLI regression fixtures. Leave installed skill dependencies unchanged. Operational examples must work with explicitly selected local inputs.

## Log

- 2026-11-25: Drafted against D012@r1.
- 2026-11-25: Started at 77f4720f1ca3d11107526210cbf9b08e9a84f1bb.
- 2026-11-25: S1 completed. The 14 public prepare tests and 58 existing trace tests pass. Preparing the real D003@r9 gate reproduced the independently obtained patch SHA-256 be8e17dd129bd885fe35ebb4aad9d13338300ee059b310a4b9640b10291c4b3a. Both installations matched their expected, distinct canonical trees. Three historical sources remain provisional.
- 2026-11-25: S2 completed. Thirteen public run tests and 72 preparation and trace regressions pass. The real D003@r9 case completed all three alternating pairs via a local protocol peer. Each assigned installation was observed three times. Resuming dispatched no extra attempts and reproduced the blind packet. The private supervisor uses POSIX advisory locks and measures only the runner subprocess.
- 2026-11-25: S3 completed. Fourteen public slice tests passed without skips on a Linux host with Bubblewrap, alongside 85 preparation, review-run and trace regressions. Verified clean test copies, SHA-1 and SHA-256 artifacts, a genuine exit 127 versus missing runtime, independent worker statuses and brief privacy. An unavailable isolation boundary leaves the criterion undecided.
- 2026-11-25: S4 completed. Fifteen public scoring tests and the 99 preparation, execution and trace regressions passed. With one common criterion, both arms can score 1/2 overall while the paired difference is +1. Repeated scoring of the real gate produced byte-identical result.json, preserved three complete pairs, withheld recall on the provisional inventory, and kept unmeasured role token counts unknown.
- 2026-11-25: S5 completed. Seven public CLI tests passed. Equal case weighting produced a 10-token difference where pooling pairs would give 5. All 624 repository tests passed across complementary runs, D001 text budgets were measured and discovery found 19 skills. Offline acceptance of the real D003@r9 gate 20261113T130221Z-45876c with candidate 8478e130d51b58bf4549f406e35ec5629118134b produced three comparable pairs from six verified dispatches. A second copy counted once. Historical recall and role token measurements were unavailable.
- 2026-11-25: Spec and Standards (GPT-6.2 Astra) and cross-family (Gemini 4 Neon) reported 34 first-round findings, merged into 25 accepted fixes. The original reviewers verified the fixes and the additional issues they found during confirmation. Regressions cover untracked named inputs, blinded source and transcript boundaries, original v1 judgments across case relocation, and unavailable build tools versus worker test failures.
- 2026-11-25: Final validation passed all 674 repository tests across complementary hosts. D001 text budgets were measured and discovery listed 19 skills. A fresh offline replay of D003@r9 produced three comparable pairs, stable scores on repeat, and one independent case after deduplication. Its three historical sources remained provisional and its role token measurements remained unknown. D012@r1 is implemented.
