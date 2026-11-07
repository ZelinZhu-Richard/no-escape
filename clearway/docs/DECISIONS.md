# Clearway decisions

## November 7, 2026 — Review of Claude's enhancements

This records planning decisions, not completed application behavior. No overnight build or model calls were started by this review.

| Decision | Reason / consequence |
| --- | --- |
| Keep road obstruction / utility work zone as the primary replay | Licensed positive footage is already available. Switching to congestion would solve a problem we no longer have and add an unverified baseline requirement. |
| Treat both older traffic clips as development candidates | Neither a filename nor dense traffic alone proves abnormal queue buildup. Human labels are still needed. |
| Limit overnight scope to replay → incident → map/evidence → confirm → responder page | Reliable integration and repeated expo cycles have higher immediate value than extra features. |
| Distinguish local completion from expo completion | No public tunnel/deployment overnight means cellular phone access cannot be claimed complete. Prepare instructions and test locally; humans validate over cellular in the morning. |
| Continue routine work with a 45-minute blocker ceiling during an authorized run | Log the selected fallback and impact. This does not waive permissions, spend limits, or protected-data rules. |
| Gemini cap means zero billable dollars | A credit-funded paid call still incurs usage. At most ten verified zero-charge smoke calls are allowed by the proposed plan; otherwise use fixtures. |
| Keep OpenAI disabled despite a $10 reserved ceiling | No defined role justifies adding a third provider. Gemini failure does not enable another paid adapter. |
| Make Claude optional, capped at $10 and five smoke requests | Deterministic evidence formatting supports the entire workflow without another model dependency. |
| Cache with model/prompt/schema/preprocessing/context provenance | A raw input hash alone can reuse stale results after configuration changes. Saved fixtures retain fixture provenance. |
| Keep YOLO optional and preserve a sampled analysis path | Vehicle counts may miss the clip's tape/debris and do not establish incident semantics. Compare gate decisions without duplicating paid calls. |
| Use simulated placement for the selected clip | Actual coordinates and camera calibration are unknown. The map can demonstrate the workflow without pretending to measure location. |
| Add fixture/unavailable analysis states | Fresh/cached alone cannot honestly describe the zero-budget fallback. Source mode and analysis mode are independent. |
| Reuse the mounted Cesium viewer; dispose on teardown | Avoid duplicate viewers and repeated initialization without leaking detached WebGL resources. Root-tile requests differ from child tile traffic. |
| Target about thirty human-labeled windows, with scene/event counts | Keep evaluation small but do not present correlated windows as independent incidents. Freeze settings; report development-only results where no separate scenes exist. |
| Retain holdout protections | Claude's proposal to remove the custodian rule is unnecessary for lean evaluation. No protected set was accessed. |
| No projection code overnight | Stubs plus geometry tests still consume implementation time. Ordinary traffic can support the later same-site calibration experiment; it cannot eliminate the calibration requirement. |
| Replace the proposed competitor attack with a product claim | No evidence establishes that all competitors need dedicated hardware or flood operators with alerts. |
| Include Pexels attribution and terms | The selected positive is not one of the older CC-licensed clips. Each media license remains separate from source-code licensing. |
| Flatten the folder as explicitly requested | Moved all eight top-level workspace entries to the project root; removed the empty wrapper; updated current footage paths and ECC installation paths. |
| Repair the existing local ECC marketplace source | Relocation changed its configured source path. Updated that source through the Codex CLI; the installed package is retained. |
| Initialize local Git on main and add origin | Target repository is empty. Remote is `https://github.com/ZelinZhu-Richard/no-escape.git`. Connection is local; no commit or push was performed. |
| Exclude local tool packages and media from project Git | Preserve existing files while avoiding accidental publication of unrelated installations, footage, and machine-local artifacts. |

## Unresolved before a real model-backed expo

- Confirm Google credit eligibility, endpoint, exact model access, and a nonzero cap if paid Gemini inference is desired.
- Run actual analysis on selected footage, inspect outputs, and save genuine cache entries.
- Submit human labels; no model-accuracy or cost-saving results exist yet.
- Repeat the verified five-cycle check after any morning changes.
- Configure a public responder origin intentionally and pass the cellular phone test.
- Verify event reuse requirements and the actual remaining schedule.

For future build decisions, append: time, affected step, observed blocker/evidence, options tried, chosen fallback, and remaining consequence. Do not record secrets.

## November 7, 2026 — Overnight build authorized

The user explicitly authorized the build, a PR, and subagents. The repository is empty upstream; create a documentation baseline on main and put application changes on a feature branch for review. No API keys or Cesium token are present in the process environment. Start in labeled fixture mode with no paid inference and a basic map fallback. No public tunnel or deployment will run.

## November 7, 2026, 08:26 UTC — Integration and review

| Step / evidence | Judgment call and consequence |
| --- | --- |
| Source references | Read pinned GEV and HawkWatch source patterns; implement Clearway freshly. No source-project application code copied. Record exact inspected links in `REFERENCES.md`. |
| Provider access unavailable | Implement a guarded Gemini Developer API adapter, genuine cache, request ledger, and explicit fixtures. Do not infer Vertex eligibility from Cloud credit. No provider requests made. Keep Claude/OpenAI/YOLO out of this run. |
| Replay assets | Use the already verified 11.111-second Pexels obstruction clip with original credit and simulated placement. Add a checksum-checked restore script; keep all media ignored. |
| Read-only handoff | Share run state through SQLite between loopback operator port 8000 and responder port 8001. Old run URLs and media expire after reset. No public endpoint exists overnight. |
| Repeatability | Five real HTTP cycles pass against both services, including deduplication, idempotent confirmation, stale actions, expired evidence, and zero inference requests. Tests do not submit human labels. |
| Review: independent gate accounting | A suppressed interval previously disappeared from gate metrics. Count local gate outcomes before filtering VLM predictions; add regression coverage for suppressed positives and reject fixture gate measurements. |
| Review: interrupted conversion | Transcode into a temporary file, validate dimensions/duration/frame count/full decode, and replace the final derivative atomically. Do not trust an existing unverified derivative. |
| Review: frontend polling | Prevent polls started during mutations from restoring stale state; invalidate pending reads at mutation completion. Allow reset during slow replay, ignore late results, and distinguish genuine negative output from fixture copy. Add focused transport-mocked regressions. |
| Map test policy | Use the explicitly labeled offline diagram for repeated automated browser cycles. Validate the default basic map separately; preserve visible linked OpenStreetMap and Cesium attribution. No photorealistic token/service access was supplied. |
| Distribution notices | Include bundled dependency licenses, Cesium notices, and Manrope OFL in build assets. Keep media/source licenses separate. |
| Browser: Cesium runtime asset paths | The static-copy plugin preserved a `node_modules` prefix, producing missing runtime assets despite a successful bundle. Explicitly strip the prefix, verify actual emitted files during every build, and confirm HTTP 200 plus the rendered map/credits in the built-in browser. |
| Evaluation | Zero human labels. Report `awaiting_labels`; do not manufacture precision, recall, model savings, or commercial results. |

The final morning report records browser results, actual spend, PR state, and remaining human work. No protected data was accessed, no organizer message was sent, and no public tunnel or deployment was started.

## November 7, 2026 — GitHub workflow authorization

The initial feature-branch push was rejected because the existing GitHub OAuth connection lacks `workflow` scope. Preserve the optional workflow as `docs/ci-checks.example.yml`, amend the unpublished local commit, and push the implementation without changing account permissions. The template is not active CI; report only the verified local checks. The application/PR work remains authorized.

## November 7, 2026 — Real Gemini follow-up

The user requested real inference on the obstruction clip and explicitly approved **$5 total**; retain the five-inference-attempt limit from the budget question. Implement a narrow paid profile for the currently documented stable `gemini-3.5-flash-lite` model. Current official rates and full context limits support a conservative $0.50 reservation per attempt. Keep failed-call reservations, separate usage estimates from unknown charges, and do not replenish limits when authorization is renewed.

Load the teammate's ignored backend `clearway/.env` privately, with literal parsing and existing environment precedence. Default the documented model/version so a key-only file is sufficient. The local authorization record derives from the user's actual approval, not a fabricated free-tier verification. The user confirmed the key has **not yet** been added; no model or account access is claimed.

Add offline readiness, a bounded model-access preflight, and a smoke command using the actual 1/4/8-second frames followed by zero-network genuine-cache verification. Include generation settings in cache identity. A model no-candidate result must remain unchanged; no label, metric, or human confirmation is fabricated.

## November 7, 2026 — Expo upgrade authorized

The user requested a new goal and implementation of visible YOLO, gate metrics, stable serving, Google 3D, public phone handoff, map-label repair, richer data points, voice, and a licensed person-in-roadway scenario. This explicitly authorizes a temporary responder-only tunnel and expands the prior overnight feature scope. It does not authorize increased provider caps, paid stock purchases, organizer messages, or a deployment.

The current launcher already omits `--reload`; the observed eight-second interruption cannot be attributed to reload without process evidence. Add durable logs and readiness, preserve loopback services, and announce the single integration restart. A prior implementation restart is a possible explanation, not a verified cause.

Clone God's Eye View under ignored `.local/references/` as a reference; keep Clearway in place. Use authentic local YOLO outputs for overlays, an explicit shadow gate baseline for estimated avoided requests, and separate actual provider spend. Use browser speech for an on-demand, evidence-grounded briefing. Public camera metadata is contextual and cannot corroborate unrelated historical stock footage.

No Gemini key or Cesium token was configured at the start of this upgrade. Token setup has been requested privately; dependent service validation remains pending. Do not claim Google 3D, real Gemini output, or a physical cellular test until observed.

The user deferred the Cesium token; prepare 3D without claiming it is active. Genuine local YOLOX-Tiny inference now supplies video overlays for all four clips. Preserve the visibly separate fixture incident narratives. The person footage is licensed Pexels roadside video showing an upright pedestrian among vehicles; reject an unsupported person-down/emergency claim and disclose its unknown exact location and camera motion.

Map context uses twenty actual NCDOT inventory coordinates from an official public dataset, preserving source/retrieval dates and no stream-availability or incident-corroboration claim. Replace Cesium glyph labels with an HTML label attached to a stable marker. God’s Eye View reference is pinned locally at `ca6eace79e60f29770597ea26871d5427b504b2b`; do not import its separately licensed data.

Review found a SIGHUP orphan risk and inconsistent custom data-directory handling in the new tunnel wrapper. Both are repaired with isolated subprocess regressions. Integration found that sandboxed sibling processes cannot signal-probe each other: an active, fresh (<=15 s) wrapper heartbeat may supply the managed origin when the PID probe is permission-denied; a missing PID, stale heartbeat, or inactive state still hides it. Keep provider secrets out of the child environment and expose only the responder.

The public HTTPS responder and QR are verified in an external browser/HTTP client; operator/config/detection/context routes remain unavailable and writes are blocked. The physical phone/cellular check has been requested from the user and is pending. No human labels or measured medical/danger classification metrics were created.

## November 7, 2026 — Physical phone test deferred

The user explicitly selected “Defer the physical phone test.” Record it as deferred, never as passed. Stop the temporary tunnel now that the immediate phone test is deferred; the foreground wrapper exited cleanly, runtime status is stopped, and the operator public origin is empty. The local server remains healthy. Reopening with `make tunnel` creates a new hostname/QR; the old public link is no longer the test target. The Cesium token was separately deferred, and the Gemini key remains absent.
