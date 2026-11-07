# Clearway table pitch

Draft for the two teammates to finalize. Use `MORNING_REPORT.md` for verified capabilities and results before presenting. The selected clip is a licensed recorded replay; the map location is simulated. Fixture analysis must be disclosed until genuine model output has been checked and saved.

## One sentence

Clearway brings recorded camera evidence, map context, visible unknowns, and a human-confirmed responder brief into one review flow.

## 90-second table script

| Time | Action | Suggested words |
| --- | --- | --- |
| 0–10 s | Show the incident desk and invite the judge to start replay. | “An operator needs more than an alert. They need to see the evidence, understand what is unknown, and hand off a clear brief. This is Clearway.” |
| 10–25 s | Start the licensed obstruction clip. Point to source and analysis badges. | “This is licensed recorded footage of a road obstruction: utility trucks, yellow tape, and debris. The map placement is simulated because the original camera coordinates are unknown.” |
| 25–45 s | Select the incident and inspect timestamped evidence. | “Selecting the incident opens the source evidence and the observations behind it. We keep unknowns visible instead of inferring a crash, injury, or exact blocked-lane count.” |
| 45–60 s | Ask the judge to confirm the demo incident. | “The operator decides whether this candidate should be confirmed. Confirmation is a recorded human action, not a second AI accuracy score.” |
| 60–80 s | Open the selected run's responder page by QR, only after cellular validation. Otherwise use local preview and say so. | “This brief is tied to this incident and this demo run. It carries the evidence and review status to the responder view. Resetting the demonstration expires the previous link.” |
| 80–90 s | State one verified result and reset. | “Our contribution is the complete evidence-to-handoff workflow with explicit provenance and repeatable state. Here is our measured result: [insert one result from the report, with its denominator].” |

At 10–25 seconds, add the sentence that matches the actual analysis mode:

- **Fixture:** “The analysis is a labeled test fixture today; it demonstrates the workflow, and real model validation is still pending.”
- **Cached genuine inference:** “These observations are saved from an actual model run on these frames; this replay makes no new inference calls.”
- **Fresh genuine inference:** “This run is analyzing the sampled frames now.” Use only when fresh inference actually occurs.
- **Unavailable:** “Analysis is unavailable for this configuration.” Do not narrate fixture observations as fresh analysis.

Do not claim “first detected,” a confirmed breakdown, live North Carolina coverage, lane-level projection, cost savings, or accuracy unless the report supports that specific claim. If labels are absent, say “awaiting labels.”

## Commercial slide draft

**Buyer hypothesis:** DOT traffic-management centers and municipal road-operations teams that review camera feeds and coordinate road response.

**Value hypothesis:** Reduce the work required to move from a candidate observation to an evidence-backed handoff. Validate this through operator review time, false-alert burden, and willingness to adopt a corridor pilot. We have not established customer demand or operational savings.

**Proposed path:** One corridor at no charge to the pilot customer, then per-camera monthly pricing if the pilot demonstrates useful operator outcomes. A free pilot still costs the team money. Pricing, procurement, service commitments, and any deployment are future decisions.

### Cost model — assumptions, not measured savings

Monthly vision cost:

`cameras × sampled windows per camera per day × days × fraction sent to model × cost per model window`

Illustration only:

| Input | Assumed value |
| --- | --- |
| Cameras | 20 |
| Sampled windows per camera per day | 120 |
| Days | 30 |
| Fraction sent to the model | 10% |
| Model cost per analyzed window | $0.002; illustrative unit cost, not a provider quote |
| Compute/storage allowance | $25/month; illustrative, not a measured bill |

The assumptions yield 72,000 sampled windows, 7,200 analyzed windows, and $14.40 in vision cost. Adding the illustrative $25 allowance gives $39.40/month, or $1.97/camera/month **before** mapping, egress, summary calls, licensing, support, engineering, and other costs. At a 100% analysis fraction, the same illustrative vision cost is $144/month. These are arithmetic scenarios; no gate has demonstrated that 10% is sufficient.

Replace the unit cost with verified pricing for the chosen endpoint and its actual image/token usage. Set the trigger fraction from evaluation. Replaying a cached expo clip does not establish fleet-wide cost reduction. Show credits separately from billable usage; promotional balances do not establish sustainable unit economics.

## Before the judge arrives

Use the same completed run the team rehearsed, with the selected positive clip and its attribution available locally. Have a tested QR on cellular or explicitly use the local-preview fallback. Choose one measured result from the final report, keep the fixture/cache labels visible, and leave time for the judge to press confirm and reset.
