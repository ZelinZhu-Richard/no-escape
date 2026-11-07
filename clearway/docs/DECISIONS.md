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

## November 7, 2026 — Additional public traffic CCTV

The user requested more live traffic-camera data points. Official DriveNC documentation requires a developer key for its camera API; the existing NCDOT/Cary inventory layers do not contain a verified public image URL. Keep the existing twenty North Carolina points honestly labeled as inventory. Add one hundred authentic Bay Area locations from the official, keyless Caltrans District 4 catalog, with county filters and selected-camera imagery. Their actual region and coordinates remain visible; they do not corroborate the Durham-placed historical replays.

Caltrans documents image-update frequency in minutes: most selected cameras publish every five minutes. Use the precise label “refreshed snapshot,” with source cadence, retrieval time, origin Last-Modified when available, and unknown capture time. This is public current imagery, not a claim of continuous live video. Only a selected preview fetches imagery; cache at the source cadence and bound network requests, permitted hosts, response sizes, redirects, and errors. Images remain in memory, are not archived or committed, and do not trigger YOLO/Gemini or incidents. Keep these routes off the read-only responder. No public tunnel, paid inference, or deployment is needed for this follow-up.

Review found that a four-image cache alone could lose the per-camera refresh deadline when switching between five cameras. Keep bounded per-camera deadlines independently of image eviction. The UI also retains a small recent-selection cache, guards response identity, and uses bounded retry intervals after throttling. Three real cameras were inspected: two traffic views (one obscured lens), one provider outage JPEG despite its catalog in-service flag. Preserve that distinction in UI/docs instead of treating HTTP 200 as camera uptime. Browser testing found the old fixed-height desktop workspace overlapped its footer after adding CCTV; let the grid grow with its content. Final verification: 186 backend tests, 33 frontend tests, production build, five HTTP lifecycle cycles, real preview selection/filtering, and 390-pixel layout passed. No model calls were made.

## November 7, 2026 — Live video, usable map clicks, and camera YOLO

The user requested actual video when available (explicitly accepting snapshot fallback), usable map clicks, and YOLO detections on camera imagery. This authorizes local camera-image inference beyond the previous viewing-only scope, without authorizing paid inference, identification, automatic incidents, public exposure, or archives. Browser reproduction found a purple pin already selected the camera but left its preview below the fold. Enlarge hit areas, add a pointer affordance, and focus/scroll the selected preview; preserve the separate North Carolina metadata pins.

Forty catalog entries advertise HLS. A bounded probe of camera `caltrans-d4-53` verified official master/media playlists, an advancing sequence, one decoded traffic segment, and permissive CORS. Use native HLS or pinned `hls.js` directly; no stream proxy is needed. Preserve a labeled snapshot fallback and stop the selected stream/sampling on teardown or page hide.

Use the existing pinned YOLOX-Tiny CPU model and bind every result to the exact JPEG hash. A real decoded HLS frame produced one car detection in about 30 ms locally; this single observation is not a performance benchmark or accuracy estimate. Low-resolution/distant objects can be missed. Show exact sampled video frames with their boxes separately from the moving player; do not invent synchronization or object tracking. The raw-frame endpoint is loopback/operator-only, type/size bounded, rate limited, and runs CPU work off the async event loop. Preserve cloud-call telemetry separately from local detection.

Browser integration played the stream initially but repeated reconnections stalled while contemporaneous official playlists remained available and advanced. Prefer the explicitly managed hls.js/MSE lifecycle where supported, with one bounded native-HLS attempt and then snapshot fallback. Explicitly load native media and ignore callbacks from the discarded engine. Record only safe numeric playback diagnostics and authored reasons, never stream URLs, response bodies, or secrets. The changed MSE path played and produced local detections in the browser; reconnect verification is recorded in the handoff.


## November 7, 2026 — Boxes on the playing live video

The user explicitly requested replacing the separate analyzed-frame panel with boxes on the moving live player. This supersedes the previous one-frame-per-second inset design. Keep hash validation, but capture the presented frame's media timestamp and allow up to eight local inference requests per second. A roughly 140 ms browser sampling interval leaves margin under the server's 125 ms limit, and only one request can be in flight. The provider stream and snapshot request cadence do not increase.

Use short-lived, same-class pairings between adjacent detections to estimate motion, redrawing against the video presentation clock. Cap velocity and extrapolation (200 ms); hide results after 350 ms of media time or 500 ms since capture, including request latency. Clear on seek, buffering, pause, page hide, camera/source changes, and fresh zero-detection results. Do not retain object identities or predict through missing detections. This is bounded motion compensation for a demo overlay, not validated tracking accuracy. Preserve the proven MSE-first player and its bounded native/snapshot fallbacks. No cloud inference or new dependencies are needed.

Verification: 218 backend and 55 frontend tests passed, including presentation-time vs. playback-time separation, late inference, no request backlog, empty detections, and seek cancellation. Production build and five real HTTP replay/confirm/reset cycles passed with zero cloud calls. Built-in-browser video showed the direct overlay at 6–6.5 local detection updates/s in a spot check, with matched video/SVG bounds on desktop and 390×844. Pause YOLO kept video playing while removing boxes; stream pause/resume cleared and restored both correctly. No second analyzed-frame image remains. Other advertised streams failed to start and fell back, and the verified camera had a later interruption; retain these provider/player availability limits in the handoff rather than claim continuous uptime.


## November 7, 2026 — Public CCTV quality correction

The user reported that live YOLO quality was poor. Actual frame inspection confirmed distant vehicles were mostly missed and camera text could receive false boxes. Comparing Tiny, larger generic YOLOX models, tiled passes, and a traffic-trained model on identical development frames showed that more frequent redraws were not a substitute for better detections. Keep the Apache-2.0 default path and upgrade live inference to pinned YOLOX-M640 independently of replay caches. It returned 13 vs. 4 vehicle detections on the 6th Street frame and 5 vs. 3 at Telegraph; these are counts, not accuracy metrics. The blurred bridge frame still has no useful vehicle detections.

A traffic-trained YOLO11s profile performed better on the clearer scene but carries AGPL-3.0 obligations. Ask the user for that concrete licensing choice, prepare the adapter, and keep it inactive pending an answer. Do not relicense the application automatically. NVIDIA alternatives were not adopted due to runtime/license constraints. No cloud inference or paid service was used.

UI skill searches had no specific match for dense CV labels; use general design judgment: enlarge the camera player, default to unobstructed boxes with a label toggle, show actual model/count/latency/resolution, and offer the clearer 6th Street view. Keep all cameras selectable and disclose provider failures and low-detail limitations. Existing hash/time identity, stale-result handling, inference concurrency and upload bounds remain.

### Approved traffic model selection

The user answered “Use the traffic-trained YOLO11 model” after being informed of the AGPL-3.0 obligation. That supersedes the pending choice above. Activate the pinned VisDrone profile, add the full license and public source links, and retain third-party notices. `make live-detect` explicitly selects the approved profile; no weights or camera imagery enter Git. Use confidence 0.40 after inspecting weak false boxes, and exclude only the observed camera689 title `[0,0,0.46,0.08]` and timestamp `[0,0.93,0.52,1]` regions by box center. Cache identity includes the camera and exclusion policy; the UI discloses them. This is development tuning, not holdout evaluation or validated accuracy.

Final development-frame counts: 6th Street 17 vehicles, Telegraph 10 vehicles after 10 graphic-centered exclusions, distant bridge 0. No human labels were created. Inference spot checks were 60.5, 54.4, and 47.7 ms respectively; counts and latency are not accuracy/uptime guarantees. Source quality is a hard remaining limit. All inference remains local with zero paid-provider requests. The service is deliberately restarted to load the selected model, with reload watching disabled.

## November 7, 2026 — Live CCTV to human review

The user explicitly requested automatic live detection candidates on the map and evidence panel. Reuse genuine local detections with conservative temporal rules: possible stationary vehicle for 12 seconds, or person visible repeatedly for 3 seconds. A person may be on a sidewalk and a stationary car may be at a signal or in ordinary traffic; name these as review signals and preserve those unknowns. No calibrated roadway ROI or semantic danger classifier exists, so do not claim either. No paid model or new provider is needed.

Retain only the exact triggering JPEG and numeric detections for each candidate, at most one per camera and 20 per run. The user's evidence request authorizes this bounded local retention; it does not create a continuous feed recorder. Reset deletes retained live evidence and invalidates old links. Keep monitoring off for snapshots, hidden/paused video, and stale input. Headers bind the real frame request to run/camera/stream/media time; the server also checks elapsed time and hash continuity. Human confirmation/dismissal is unchanged and never automatic. Existing public-tunnel and physical-phone deferrals remain.

Integration found that replay source/mode changes previously reset the whole run. With live evidence now in the same queue, that would silently erase unrelated candidates. Preserve the run while browsing replay sources or changing mode; reserve whole-run clearing for the explicit Reset demo control. Source preview selection is not overwritten by background polls.

Verification: 284 backend and 66 frontend tests, production build, and five HTTP replay lifecycles passed. A separate visibly synthetic browser environment exercised map → frozen evidence → confirm → responder → reset expiry, including mobile image/box alignment; its process was stopped and its data never entered the real demo state. Genuine 6th Street video ran the monitor at about six local detection updates/s, with no candidate in the checked interval. No natural-incident accuracy is inferred. Pause-alerts preserved playing video/detections, and re-enabling started fresh continuity. One announced no-reload server restart loaded the feature; provider requests/spend stayed zero.

## November 7, 2026 — Codex review before merge

The user explicitly requested fixing Codex review findings and merging PR #1. Marking the PR ready triggered the GitHub Codex review, which found replay source/playback mismatch and restoration ignoring `CLEARWAY_DATA_DIR`. A local read-only Codex review of main-to-HEAD independently reproduced those and found a third issue: run-global inference provenance appearing on an unrelated, unanalyzed clip. Address all three before merging; existing deferred credentials, 3D setup, physical phone test and human evaluation remain documented product limits rather than new approval gates.

Bind autoplay to a source/run request and invoke it only on the mounted matching video. Navigation/reset cancels that request, and late replay responses retain operator focus. Associate no-candidate analysis results with their source/run in this view instead of guessing the source of a global result after reload. Untouched previews show “Not analyzed in this view”; actual incidents continue to use stored provenance. Both media restoration commands use the shared private configuration loader and write their receipts beside the configured footage directory; run them through the existing application virtual environment.

Verification: 290 backend tests, 72 frontend tests, production build and emitted asset/license checks passed. Added twelve regression cases without downloads or provider calls. The built-in browser reproduced the queue/source mismatch and verified that Start replay now plays the requested obstruction clip with advancing time. GitHub has no active required CI checks; these are local results. No paid inference, deployment or public tunnel was started.

The follow-up GitHub review found that an idempotent replay still returned the last run-global result, which could overwrite a source-specific cache miss with another clip's cache hit. Persist analysis on each job, migrate the existing schema under a serialized transaction, and include the current run's per-source analysis map in every state snapshot. Replay responses select the requested job's status in the same read transaction and reject a reset before response. The UI reads that map for initial load, repeated replay and polling; it no longer assigns global response analysis to a source locally. Legacy jobs without a stored result are explicitly unavailable rather than reconstructed from unrelated state. Existing incident provenance remains intact.

Final validation: 294 backend and 75 frontend tests, production build and emitted assets passed. Seven additional regressions cover mixed source outcomes, idempotency, concurrent pending/completed jobs, restart, legacy migration, reset and polling. An announced no-reload restart loaded storage changes; HTTP checks confirmed the existing run and two fixture candidates survived and repeated replay returned the requested legacy status without provider calls.

## November 7, 2026 — Verify the teammate's Dispatch UI

The user requested checking the merged UI and testing CCTV detections through map/evidence/confirmation. Fetch and fast-forward the clean checkout to the merged Dispatch design, preserving its visual direction. Fix functional regressions on a separate PR branch: reveal evidence after explicit desktop map/queue selection, use a neutral idle headline, retain measurement/error disclosures, and give live-evidence metadata a readable surface. Polling must not steal scroll/focus.

Preserve existing real evidence while testing: run actual public streams, installed YOLO weights and unchanged temporal rules in a separate local database. Each of two two-minute checks produced no new candidate; do not lower thresholds or seed an alert and call it a natural result. Use controlled detector API tests for deterministic positive creation, then verify the already-retained genuine 6th Street candidate's map/evidence/confirmation/responder path in the rebuilt interface. The user explicitly requested confirmation testing; this changes only the local review status and never dispatches assistance.

Verification: 294 backend and 78 frontend tests, production build and license/assets passed. Real streams showed about 6–6.5 updates/s; the retained live candidate's 12.046-second/75-frame provenance and exact image hash remained intact through confirmation. Desktop and 390 px operator/responder checks passed. The isolated server was stopped, the actual demo evidence retained, and cloud calls stayed zero. Detailed distinctions and artifacts are recorded in DISPATCH-VERIFICATION.md.

## November 7, 2026 — Fremont and Dense traffic detection correction

The user reported missed vehicles on Fremont and then added the Dense traffic source. Browser checks separated healthy video playback from weak model results. On three matched Fremont development frames at the browser's aspect-corrected 640×480/JPEG80 input, installed VisDrone returned 1/4/0 boxes and installed YOLOX-M returned 10/13/7 with visibly better near/mid-distance coverage. Use an explicit Fremont-only model selection rather than silently switching the global model or lowering confidence. The local selector supports bounded camera overrides, checksum-pinned profiles and preserved global/other selections. Model metadata, preprocessing, thresholds and selection enter provenance; missing weights fail without substitution. Keep one shared inference slot and per-profile runtimes/cooldowns.

Dense traffic plays correctly, but its saved Tiny cache had six boxes across 45 samples. Use approved VisDrone only for this aerial source, regenerate genuine timestamped detections, and leave the other replay cache contracts intact. Matched 1/4/8-second frames went from zero to 69/41/51 boxes. Inspection found remaining false lane-marking boxes and overlaps; report development counts without accuracy claims. Keep the existing no-candidate fixture outcome and display that selected-source result explicitly even with unrelated incidents in the queue. Restore readable result disclosures. Browser inspection showed crowded confidence labels obscuring cars, so make replay labels optional and default them off for Dense traffic; boxes remain visible.

Verification: 316 backend and 86 frontend tests, production build and license/assets passed; independent reviews found no material issues. Actual Fremont playback and rebuilt Dense replay were checked in the visible built-in browser. Existing incident evidence survived two announced integration restarts. No paid calls, new model downloads, fabricated alerts, public tunnel or deployment. The development segment, diagnostic images, local model selections and genuine detection cache stay ignored; documentation records setup and remaining limits.

## November 7, 2026 — Dense tiling and live ByteTrack

The user authorized tiled Dense inference, live ByteTrack, same-footage tests and the existing PR update. Keep Dense-only native-pixel 768px tiles, nominal 25% overlap, full-frame pass and .50 output floor after comparing full-frame .40/.50 controls. Reject internal-boundary fragments and merge duplicates conservatively; preserve person/vehicle separation. Bind geometry/settings to caches; keep other replay caches unchanged and explicit full-frame fallback. Forty-five samples take 17.074s to prepare locally. Counts and visible coverage improve on the inspected frames, but roof/background false positives and occlusion remain; no labeled accuracy is claimed.

Adapt the pinned MIT ByteTrack core with NumPy-only global assignment and Kalman prediction. Keep high/low association, tentative confirmation and short lost recovery; no prediction-only output. Separate the 0.10 tracking candidate pool from raw high-confidence detections/counts and all incident evidence. Keep ephemeral stream IDs, bounded sessions and clocks, repeat-frame tombstones, and strict client source/hash/config/time validation. Paused alerts preserve tracking but clear monitor continuity, including a pending pause through a rapid toggle. This supersedes earlier statements that the live display only uses adjacent greedy pairings.

The same 58-frame Fremont segment produced 461 unchanged high detections plus 77 current low-score recoveries; 13 IDs crossed high→low→high. Tracking median 0.560ms, maximum 2.308ms. This is a development continuity diagnostic, not identity accuracy or natural-event recall. No training, cloud inference, model download, deployment, tunnel, database reset or human labels are required by this work.

## November 7, 2026 — Bay Area-only public CCTV

The user asked to remove NC cameras and add Bay Area endpoints. The official District 4 feed contains 773 records, including three outside the nine-county Bay Area and three reported out of service. Retain 767 validated in-service camera records, including 191 advertised HLS endpoints and 576 snapshot-only entries. Enforce county, region-ID, geographic and URL checks on both import and saved-catalog reads. Raise the metadata bound to 1,000 records/2MB; retain selected-camera rate limits and bounded image/detection caches.

Remove the unused NC inventory layer, metadata file, API route, refresh script/Make target and parser/tests. Preserve honest simulated Durham replay placement and all retained live incident evidence. The public list shows 50 matches then 50 per request; all matching camera pins remain selectable and fit the map bounds. Do not imply all advertised streams were tested or working. No paid inference, new provider credentials, continuous archive or public tunnel is introduced.

Verification: 386 backend and 111 frontend tests, production build and asset checks passed. Built-in-browser checks covered 50→100 list pagination, the Santa Clara filter, a new SR-237 map pin opening actual 1280×720 video with YOLO/ByteTrack, and full-network fitting. All four prior incidents survived the announced restart; the selected new feed later generated one additional unconfirmed candidate through the existing rule. No natural emergency or alert accuracy is established. Endpoint availability varies: two of three new master-playlist probes succeeded, and only SR-237 was checked for playback.
