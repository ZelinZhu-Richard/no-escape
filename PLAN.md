# Judging Criteria

1. **Technical Sophistication**
   Advanced AI use and software application

2. **Novelty**
   Creative, unique, and differentiated from existing solutions

3. **Commercial Viability**
   Clear path to monetization and sustainability

4. **Presentation**
   Quality of pitch and demo

# Technical Tracks

## Robotics

Build with sensors, actuators, and control systems. Anything that senses or moves in the physical world.

## Computer Vision

Build with images, video, or camera input. Detection, tracking, generation, anything that reads the visual world.

# Industry Tracks

## Health & Wellness

Mental health, physical fitness, or clinical tools. Build something that makes a person healthier.

## Social Impact & Education

Change how people learn or how communities solve shared problems. Tutoring, accessibility, civic tools, all fair game.

## Finance, Enterprise & Tech

Tools that help a business run better. Ops, analytics, workflow automation, fintech.

## Entertainment, Media & Arts

Creative tools, new formats, anything that changes how people make or experience art.


# Clearway: Revised Build Plan

Updated November 7, 2026. This revision adopts the useful parts of Claude's overnight enhancements and corrects them for the licensed obstruction footage now available. The user authorized unattended implementation, a PR, and subagents on November 7, 2026. Build status and verification will be recorded in MORNING_REPORT.md; genuine model inference remains subject to the stated caps.

## Confirmed constraints

- Two people, a 30-hour total build budget, table-expo judging, no robot or drone.
- Available balances: $200 Claude API, $100 OpenAI API, and $100 believed Google Cloud billing credit. Provider balances are not interchangeable; Cloud eligibility is unverified.
- Use existing licensed footage. The team will not film a staged vehicle scene.
- For this project, work directly in the repository root. The user explicitly removed the `workspace/` requirement. Application files remain organized under `clearway/`.
- Protect any designated `holdout/` data under the existing custodian rule. This review does not access holdout or create a protected evaluation set.
- Current authorization: build unattended following this plan, use the two repositories as references, use subagents where useful, and create a PR. Deployments, public tunnels, organizer contact, and paid calls beyond the specified caps remain excluded.

**Product:** Clearway connects a possible road obstruction to visual evidence, a map view, human confirmation, and a phone responder brief.

**Working pitch:** “Clearway turns existing camera footage into an evidence-backed incident an operator can review, confirm, and hand off.”

## Decisions on Claude's enhancements

| Items | Decision |
| --- | --- |
| 1–4: narrow scope, unattended judgments, fallbacks, no external publishing | Adopt for the authorized overnight build. Continue reversible work using documented fallbacks, within permissions and budgets. Timebox a blocked step to 45 minutes at most. No deployments, organizer messages, or public tunnels during that run. The separately authorized GitHub PR is allowed. |
| 5–6: congestion instead of obstruction | Do not adopt. The missing-footage premise is resolved: a licensed obstruction clip is downloaded and visually checked. Retain road obstruction / utility work zone as the primary demo class. |
| 7: YOLO gate plus Gemini | Optional after the core flow. Vehicle counts are not evidence of abnormal congestion without a comparable baseline and motion evidence. A vehicle gate may miss debris/tape; it must not be the only way the obstruction reaches analysis. |
| 8: real vs. simulated map placement | Adopt. Use real coordinates only with source evidence. Selected obstruction footage has unknown coordinates; label its demo marker simulated. A known camera location is still not a measured object location. |
| 9–12: budgets, caching, provider fallback, secrets | Adopt with strict zero-dollar interpretation: no paid Gemini calls at a $0 cap. No automatic provider substitution. OpenAI remains an unused reserve. |
| 13–15: reset, polling, run-specific QR, status labels | Adopt. Add fixture and unavailable analysis states so they cannot be confused with fresh or cached model inference. |
| 16: Cesium lifecycle and request counts | Adopt the intent. Keep one viewer for the mounted map, reuse it across demo resets, and dispose correctly when removed. HMR may require recreation; avoid leaks. Track root requests separately from tile-content traffic. |
| 17–20: lean evaluation | Adopt about 30 human-labeled windows, one labeler, frozen settings, counts and denominators. Freezing does not erase development leakage; do not delete holdout protections or count many windows from one event as independent incidents. |
| 21: pitch and commercial draft | Adopt the deliverables. Replace unsupported competitor generalizations with a claim about Clearway's own demonstrated workflow. Pricing and savings remain hypotheses until measured. |
| 22: attribution | Adopt and include the selected Pexels clip, not just the two older Creative Commons clips. |
| 23: projection stub and tests | Defer all projection coding until the core flow is reliable. An ordinary-traffic snapshot can support calibration, but valid camera/road correspondence is still required. |
| 24: morning report | Adopt. Report local completion separately from the cellular phone test, and distinguish fixtures from actual model output. |

## Overnight scope and completion levels

The only required interaction is:

**replay → incident candidate → map marker → evidence panel → confirm → responder page via run-specific QR**.

Projection, voice, weather, extra incident classes, mandatory multi-camera collection, live-source corroboration, and additional agents are outside the overnight critical path. Claude evidence rewriting and YOLO gating are optional only after the interaction and reset tests pass.

Two completion levels must remain separate:

1. **Local workflow ready:** replay and a clearly labeled analysis result drive the map, evidence, confirmation, and mobile-layout responder page in the built-in browser. Five complete cycles pass. If only fixtures are available, report “workflow ready with fixtures; model validation pending.”
2. **Expo ready:** actual inference on cleared footage has been checked, saved outputs replay correctly, and a human has opened the responder page on a phone over cellular using an intentional public HTTPS connection. No deployment/tunnel tonight means this level remains a morning task.

Never describe a local `localhost` QR as accessible to the judge's phone. If `PUBLIC_BASE_URL` is unset, show “Local preview — phone access not configured” and a local preview action; enable the public QR only when configured.

## Footage and primary incident

**Primary: possible road obstruction / utility work zone.**

- [Utility Workers Clearing Storm Debris on Road](https://www.pexels.com/video/utility-workers-clearing-storm-debris-on-road-30567549/), Ibrahim Bennett, [Pexels License](https://www.pexels.com/license/).
- Local replay: `clearway/data/footage/road-obstruction-demo.mp4`.
- 11.1111 seconds, 1920×1080 H.264, 333 frames, approximately 11.8 MB. Full playback speed and duration retained; all frames decoded successfully.
- Visible evidence: utility trucks occupying the roadway, yellow tape across it, and branches/debris on pavement. It shows an already managed obstruction, not a newly detected breakdown or incident onset.
- Suggested analysis samples: 1, 4, and 8 seconds. The human-reviewed reference is in `clearway/docs/demo-scenario.json`; it must never be passed off as model output.
- Coordinates and capture time are unknown. Source-page publication date is not capture time. Demo map placement is explicitly simulated; current DriveNC events cannot corroborate this historical scene.
- One clip is one demonstration event. Looping does not extend the observed incident duration or establish accuracy.

**Control candidate:** `street-traffic.webm`, 35 seconds, [Street traffic](https://commons.wikimedia.org/wiki/File:Street_traffic.webm), Editor, CC BY 3.0. Finish human window labels before claiming a no-alert control. Its listed coordinates are camera metadata, not a calibrated incident location.

**Other development footage:** `traffic-jam.webm`, 11.2 seconds, [Traffic Jam](https://commons.wikimedia.org/wiki/File:Traffic_Jam.webm), Melvin Loi, CC BY-SA 2.0. Sampled frames show dense traffic. The title does not establish abnormal congestion or queue buildup; there is no verified same-camera normal baseline. Do not make it the positive by decree.

Sources, checksums, rejected alternatives, and license links are in `clearway/docs/footage-sources.json`. Keep media ignored in Git. Display replay credit in the app; the Pexels asset retains its own terms, including restrictions on standalone redistribution and misleading endorsement. See `clearway/docs/DEMO-FOOTAGE.md` and `clearway/docs/ATTRIBUTION.md`.

## Technical slice

Use a fresh Vite/TypeScript frontend with Cesium and a small Python FastAPI/Pydantic service with SQLite. Add OpenCV/local detection only where needed. Pin versions when the implementation works. No orchestration framework or second language model is required to complete the first slice.

### State and contracts

- Every run has a new `run_id`. Every incident has an `incident_id`, source ID, evidence references, and a location quality of `known_camera`, `approximate_zone`, `simulated`, or `unknown`.
- Source mode: `recorded_replay | live | synthetic`.
- Analysis mode: `fresh | cached | fixture | unavailable`. Cached means a saved genuine model response with provenance. A saved fixture stays a fixture.
- Review status: `candidate | confirmed | dismissed | resolved`. Confirmation is a human action, not automatic accuracy.
- Preserve frame time within the clip, fetch time where applicable, original capture time if known, and an explicit unknown value otherwise.
- Repeated observations update the same candidate within the same run/source/event. Confirmation is idempotent. Reset invalidates prior run selections, jobs, timers, and QR targets.
- Async responses carry their originating run ID. Ignore late results for old runs, including in the map and phone view.
- Any external context has its own status: `matched | no_match | unavailable | not_applicable`. Historical nonlocal replay defaults to `not_applicable`; never fabricate a matching report.

### Vision and cache

Implement the Gemini adapter and typed response validation, with the model ID and billing endpoint explicitly configured. The previously selected Gemini model remains provisional until account access and endpoint support are verified; do not guess an available model ID or silently switch providers.

For the first genuine inference, use short timestamped frame sequences from the selected clip. Ask for observable road conditions and evidence references; allow unknown classification, location, and lane count. Do not infer an engine failure, collision, injury, or precise location from this scene.

Cache by provider, exact model/version, prompt version, response-schema version, preprocessing version, ordered frame hashes and timestamps, and relevant context/calibration inputs. Input hash alone is insufficient when prompts or models change. Preserve provider usage and provenance with each genuine response. Store failures separately rather than as successful cache entries.

Frozen replay is network-inference-disabled from startup, including retries and summarization. On a cache miss, show unavailable or an explicitly selected fixture; never make an automatic paid call. Tests should assert zero outbound inference requests. This does not mean map tiles work offline.

### Optional local gate

Only attempt the gate after the five-cycle local flow works. Timebox integration to 45 minutes initially. A detector may produce vehicle counts and road-region occupancy, but these are candidate signals, not proof of an incident. Baselines must be source-specific; the two unrelated traffic clips cannot provide a shared normal baseline. Camera motion or changing zoom invalidates a fixed image-space region.

The selected obstruction may have low vehicle count and non-vehicle evidence, so retain an explicit sampled/manual analysis path. For the expo, the chosen clip can run through the ordinary sampled path. Report that path honestly rather than pretending the gate triggered it.

Measure hypothetical requests avoided by replaying gate decisions over identical windows; do not double paid calls merely to compare gate on/off. Separate measured gate decisions, hypothetical savings, cache hits, and actual billed calls. Review the selected detector/weights license before adoption; [Ultralytics documentation](https://docs.ultralytics.com/) describes its licensing options.

### Map

Load photorealistic 3D tiles if the existing account/token permits it. Preserve required attribution. If setup takes 45 minutes without a working view, use a basic Cesium globe with the same marker/evidence interaction; if WebGL fails, use a labeled local map fallback with the same selection behavior.

Maintain one viewer for the mounted map and update entities on replay/reset. Do not reset the scene by constructing another viewer. On actual teardown, call the documented [Viewer.destroy](https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html#destroy). Keep HMR handling explicit and leak-free rather than promising that a viewer can survive every full page reload.

The [Cesium ion pricing page](https://cesium.com/platform/cesium-ion/pricing/) lists 1,000 monthly Google photorealistic root-tile requests for the eligible Community plan. This is not a 1,000-total-tile allowance or a promise of unlimited usage. Record viewer/tileset initializations and observable root requests separately from child tile requests. Check the provider dashboard for billing/quota truth; do not log signed URLs or tokens. Use the basic map for routine fixture tests.

### Phone handoff

The QR identifies the selected incident and current run, for example `/respond/{run_id}/{incident_id}` under configured `PUBLIC_BASE_URL`. Poll a small read-only status endpoint every two seconds, with bounded error backoff. After reset, old runs return a clear expired state; they must never resolve to the newest incident.

Serve the responder HTML, selected evidence, and read-only API under one origin. Keep confirmation/reset/admin controls off the public responder surface. Do not expose the full footage archive or local filesystem. The morning runbook must specify how to expose only that surface and how to stop the tunnel.

Prepare instructions only during the overnight run. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) have changing hostnames, no uptime guarantee, and no SSE support. Regenerate the QR after URL changes. Morning validation: disable phone Wi-Fi, scan the QR, confirm on the laptop, observe the status change, reset, and prove the old run expires.

## Spend controls

These are ceilings for a future authorized build, not spending performed by this planning task.

| Service | Overnight cap | Enabled use |
| --- | --- | --- |
| Gemini | $0 | Adapter + fixtures by default. At most 10 smoke calls only if the exact route is verified to incur zero billable usage; otherwise zero calls. Cloud credits do not make billed usage zero. |
| Claude API | $10 | Optional brief synthesis only after the core flow; at most 5 smoke requests with verified pricing and configured credentials. Deterministic evidence formatting is the default fallback. |
| OpenAI API | $10 reserved ceiling | No application dependency or enabled calls. This reserve is not a Gemini fallback. |
| Hosting / paid tiles | $0 | Local-only overnight. Use eligible existing free access or the basic map fallback. |

At least 90% of automated checks use fixtures; core correctness/reset tests use no paid model calls. Never make a real call merely to meet a test percentage.

`clearway/data/spend-ledger.jsonl` records provider/model, request ID/hash, request time, status, usage, estimated charge, retries, cache behavior, and known price basis. Reserve worst-case estimated cost before concurrent requests; fail closed if pricing is missing or the cap would be exceeded. Distinguish billable charge from out-of-pocket charge after credits. Unknown costs are unknown, not zero. Local Codex session usage is not automatically spending from the user's API balances.

If Gemini access or zero-charge eligibility fails, keep the adapter and fixtures, log the limitation, and continue the workflow. Paid Gemini validation requires a later explicit nonzero cap. Never print, log, or commit secrets; sanitize provider errors and secret-bearing URLs. No outbound messages, organizer contact, deployments, or public tunnels during the overnight run.

## Build sequence and fallbacks

Use the actual clock and official event cutoff. These are relative phases, not a promise that a full eight hours or thirty hours still remains.

| Phase | Work | Verification |
| --- | --- | --- |
| First 45 minutes | Read project instructions; initialize app skeleton; agree on schemas; load selected replay; create decisions/spend logs | Local startup and playable footage; real vs. fixture state visible |
| Hours 1–2 | Replay input, typed observation fixtures, incident storage and run lifecycle; map shell and marker | Repeated observations yield one candidate tied to correct evidence |
| Hours 2–4 | Evidence panel, confirmation, responder page, two-second polling, selected-run URL | Full local interaction; no fabricated model provenance |
| Hours 4–6 | Cache-only replay, stale-result isolation, reset, expired-run handling, browser integration tests | Five full cycles pass; reset under 15 seconds; zero inference calls in frozen replay |
| Hours 6–7 | Optional eligible provider smoke check; small labeling/eval interface; gate only if core is stable | Actual results distinguished from fixtures; labels/metrics remain pending when absent |
| Final overnight hour | Startup/runbook, attribution, pitch draft, morning status and known risks | Reproducible local handoff; exact commands reflect implemented files |

Person A owns map/evidence/phone UI; Person B owns replay/API/cache/run lifecycle. Both inspect the full loop. The user has now also authorized subagents; coordinate them on bounded components with the same project restrictions.

For any step blocked for 45 minutes, log the blocker, attempts, chosen fallback, and remaining impact in `clearway/docs/DECISIONS.md`; continue independent work. Switch earlier when the cause is clear. A fallback must not bypass permissions, billing caps, or data restrictions.

- Model blocked: labeled fixtures and unavailable state; no provider switch.
- Photorealistic tiles blocked: basic map, preserving evidence selection.
- YOLO blocked or unsuitable: ordinary sampled analysis path; no gate savings claim.
- Claude blocked: deterministic evidence summary with unknowns.
- Public phone access unavailable: local mobile preview and prepared instructions; expo cellular test stays pending.
- Behind schedule: cut optional gate, summary model, collection, and decorative UI before cutting reset, provenance, phone flow, or tests.

## Meaningful verification

Build a five-cycle integration script using the actual app/API plus browser checks, not an isolated mock state machine. Each cycle should start replay, wait for its candidate, select its marker, inspect evidence, confirm, read the responder route, and reset. Assert:

- Exactly one intended incident for the positive run, no duplicate confirmation, and the selected evidence matches the clip/run.
- The responder reflects confirmation and the current run; a second incident selection does not redirect another QR.
- Reset finishes within 15 seconds, leaves no active old incident, and invalidates the old responder link.
- Late analysis responses, stale polling, double clicks, and replay restart cannot repopulate the old run.
- Frozen replay makes zero network inference calls, including after reset and cache miss.
- Unavailable providers, unlabeled controls, and simulated placement stay visible.

Fixture tests validate workflow behavior, not real detection. Run automated tests through terminal tools and all visual/browser checks in the built-in visible in-app browser. Do not open personal browser windows.

## Lean evaluation

Target about 30 labeled windows from one human labeler if useful footage exists. The selected positive clip and the two existing traffic clips remain development/demo material because they have already been inspected. Thirty windows from these few clips are not thirty independent events.

Build a small labeling interface with scene/clip ID, interval, observable condition, uncertainty, and reviewer. Human labels start empty. A model must not invent ground truth. With no submitted human labels, the evaluation report says **awaiting labels**. The existing agent-reviewed reference scenario is not a replacement for those labels.

Freeze code commit/config, thresholds, ROI/baseline, prompts/model, and manifest before the final run. Tune on development scenes only. Use different whole scenes or camera/time blocks for evaluation where available. If only development clips exist, call the result a development demonstration, not held-out accuracy. Do not create a new holdout process merely for this small demo; any existing protected holdout still follows the custodian rule.

Report plain counts and denominators:

- False alerts on labeled normal windows, with windows and independent scenes counted separately.
- Known-positive gate coverage, e.g. detected X of Y labeled positive windows across Z events. With one positive event, identify it as a single-event diagnostic; do not generalize recall.
- Gate-passed/total candidate windows, hypothetical requests avoided, actual network requests, and cache hits separately.
- Median and maximum processing latency with n, separately for fresh, cached, and fixture paths. Source-refresh delay is a separate quantity. This clip has no observed incident onset, so real onset-to-alert delay is not measurable.
- Billable cost per analyzed window and per distinct replay; distinguish estimates from recorded usage and credit offsets.
- Duplicate incidents and reset times across the five-cycle test.

No F1 confidence intervals, fabricated labels, or invented savings. If no natural incidents were recorded, say **recall not measurable on natural data**. A human-confirmed result is not automatic model accuracy.

Live DriveNC collection is a later optional source of independent examples, not a prerequisite tonight. If added, use the [documented developer access and rate limits](https://www.drivenc.gov/developers/doc), record freshness, and label failures. Do not claim a recorder is running until it is verified.

## Morning work and projection

Morning priorities:

1. Check what actually works, review `MORNING_REPORT.md`, and start the app using its tested commands.
2. Verify Google credit/service/model access. Set an explicit nonzero Gemini cap if paid validation is wanted; current cap permits no billed calls.
3. Run genuine inference on the positive/control, inspect output, and save genuine cache entries. Keep fixtures available as labeled fallbacks.
4. Intentionally start the documented public responder connection, configure its HTTPS URL, regenerate QR, and test on a phone over cellular.
5. Complete human labels and the frozen evaluation; report the actual sample size.
6. Seek organizer clarification about source-project reuse if still relevant. The assistant sends no organizer messages.
7. Attempt the one-camera projection experiment only after the above core path is healthy.

**Projection: Person A, reserved hours 10–16 if still feasible before the actual deadline.** No projection stub or geometry tests are required overnight. Calibration can use ordinary traffic from a fixed live DriveNC view; it does not require incident footage. It does require the same physical scene in the image and 3D map, a stable camera pose, camera height/orientation/FOV estimates, and visible road reference points.

During that later slot: implement pixel-to-ray geometry with explicit coordinate conventions; reject invalid/no-hit/above-horizon rays relative to the chosen road model; validate unused road landmarks and lane/shoulder placement. Camera rotation matters, so “above horizon” is not merely a fixed image row. Keep ground-contact estimation distinct from full 3D reconstruction. A private Cesium ray-picking API is not a guaranteed stable one-call solution; isolate and validate any such dependency.

Stop at hour 16 if independent checks fail. Keep the labeled camera/zone marker and devote remaining time to the expo. Unknown-location stock footage cannot validate real-world lane projection.

## Pitch, commercial hypothesis, and deliverables

Draft `clearway/docs/PITCH.md` with a 90-second table script and this defensible novelty line:

“Clearway brings recorded camera evidence, map context, visible unknowns, and a human-confirmed responder brief into one review flow.”

Do not claim all existing camera AI requires dedicated hardware, fixed angles, or floods operators with alerts. Do not claim arbitrary-camera robustness, conflicting-source resolution, or reduced false alerts before implementation and evaluation support it.

Buyer hypothesis: DOT traffic-management centers and municipal road-operations teams. Proposed route: one-corridor pilot at no charge to the customer, then per-camera monthly pricing if operator value and operating cost justify it. A free pilot still costs the team money; it is a future commercial proposal, not an authorized deployment or expense.

Cost model: cameras × sampled windows/camera/day × days × trigger fraction × inference cost/window, plus any summary calls, mapping, compute, storage, egress, support, and license costs. Mark all inputs assumed or measured; include always-on sampling and no-gate cases. Cache savings in a repeated expo clip are not representative of a live fleet. No invented customer validation, pricing commitments, or profitability claims.

Prepare during the build:

- `clearway/docs/DECISIONS.md`: judgment calls, blockers, fallbacks, unresolved assumptions.
- `clearway/docs/ATTRIBUTION.md`: GEV/HawkWatch inspiration, actual reused dependencies/code, and every clip's separate license.
- `clearway/docs/PITCH.md`: product claim, commercial hypothesis, and 90-second script; humans finalize.
- `clearway/docs/TUNNEL.md`: exact commands for the implemented read-only responder surface, URL configuration, cellular test, and shutdown; do not start it overnight.
- `clearway/docs/MORNING_REPORT.md`: works/partial/failed, exact tested startup/test commands, actual spend and request counts, fixture vs. genuine inference status, test evidence, ordered human tasks, and demo risks.

Morning report must not list the QR handoff as cellular-verified unless the phone test happened. No made-up run commands for files that have not been implemented.

## Event rules and judging

The [Triangle AI Hackathon FAQ](https://triangle-ai-hackathon-site.vercel.app/faq) previously reviewed for this plan says one track and no reuse of prior projects. Choose **Computer Vision** and build a fresh application with credited inspirations. MIT permission does not decide event eligibility. No organizer clarification has been obtained.

The previously checked [schedule](https://triangle-ai-hackathon-site.vercel.app/schedule) lists November 8, 2026: hacking ends 8:30 AM Eastern, submission 9 AM, judging 10 AM. Recheck announcements before execution; use remaining time rather than assuming thirty hours are still available.

| Judging criterion | Demonstrable evidence |
| --- | --- |
| Technical Sophistication | Genuine visual analysis when enabled, structured evidence, incident lifecycle, caching, and run-safe handoff |
| Novelty | The team's implemented review-to-handoff interaction and measured improvement, with source inspirations disclosed |
| Commercial Viability | A clear operator/buyer hypothesis and explicit operating-cost assumptions |
| Presentation | A 90-second interaction, visible replay/provenance, phone handoff, and reliable reset |

## Repository layout and current status

```text
no_escape/
  AGENTS.md
  PLAN.md
  clearway/
    docs/                 # plan decisions, footage sources, scenario, attribution
    data/                 # local media/cache/ledger, ignored in Git
    web/                  # React/Cesium interface and frontend checks
    api/                  # FastAPI operator, responder, analysis, and storage
    tests/                # API, budget/cache, evaluation, and media checks
    scripts/              # local launcher, media restore, cycle verification, evaluation
  ECC/                    # existing local tool checkout, ignored in project Git
  ECC-codex-reviewed/     # existing local plugin package, ignored in project Git
```

Repository remote: [ZelinZhu-Richard/no-escape](https://github.com/ZelinZhu-Richard/no-escape). The documentation baseline is on `main`; the authorized overnight implementation is on `feat/clearway-overnight-demo` for a draft PR. Keep downloaded footage, caches, credentials, and unrelated tool-installation artifacts out of commits.

Current implementation: the local operator/responder applications, licensed replay, evidence review, confirmation/reset lifecycle, human-labeling UI, fixture/genuine-cache separation, guarded Gemini Developer API adapter, evaluation script, and startup/media-restore tools exist. Actual model inference, human evaluation labels, public phone/cellular validation, photorealistic-service validation, and projection remain unfinished. See [MORNING_REPORT.md](MORNING_REPORT.md) for final tested behavior, commands, limitations, and PR status. Fixtures do not establish Computer Vision performance.
