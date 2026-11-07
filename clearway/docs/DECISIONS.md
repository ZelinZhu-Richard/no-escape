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
- Build and verify five complete replay/confirmation/reset cycles.
- Configure a public responder origin intentionally and pass the cellular phone test.
- Verify event reuse requirements and the actual remaining schedule.

For future build decisions, append: time, affected step, observed blocker/evidence, options tried, chosen fallback, and remaining consequence. Do not record secrets.

## November 7, 2026 — Overnight build authorized

The user explicitly authorized the build, a PR, and subagents. The repository is empty upstream; create a documentation baseline on main and put application changes on a feature branch for review. No API keys or Cesium token are present in the process environment. Start in labeled fixture mode with no paid inference and a basic map fallback. No public tunnel or deployment will run.
