# Clearway table pitch

Draft for the two teammates to finalize. Use `MORNING_REPORT.md` for verified capabilities before presenting. YOLO overlays are genuine saved local inference; semantic incident narratives remain explicit fixtures until Gemini validation. The source is licensed recorded footage and its map placement is simulated.

## One sentence

Clearway brings recorded camera evidence, map context, visible unknowns, and a human-confirmed responder brief into one review flow.

## 90-second table script

| Time | Action | Suggested words |
| --- | --- | --- |
| 0–10 s | Start **Person in roadway**, seek to 4 seconds. | “There is a person among moving road traffic. Who sees the evidence, who reviews the uncertainty, and how does the next person get a clear brief?” |
| 10–25 s | Show the person/vehicle boxes and counts while the clip plays. | “These boxes come from real local YOLO inference, saved at four samples per second and synchronized to this licensed replay. Detecting a person does not prove injury or danger.” |
| 25–45 s | Point to the analysis badge, evidence times, unknowns, and map. Optionally play a short voice brief and stop it. | “Our incident narrative is a labeled fixture while Gemini setup is pending. The operator can inspect the actual video, hear the brief, and see what remains unknown. The map placement is simulated; the cyan pins are separate official camera inventory.” |
| 45–60 s | Ask the judge to confirm the demo incident. | “The operator decides whether this candidate should be confirmed. Confirmation is a recorded human action, not a second AI accuracy score.” |
| 60–80 s | Open the selected run's responder page by QR, only after cellular validation. Otherwise use local preview and say so. | “This brief is tied to this incident and this demo run. It carries the evidence and review status to the responder view. Resetting the demonstration expires the previous link.” |
| 80–90 s | State the verified lifecycle result and reset. | “Five repeated handoff/reset cycles passed. The old brief expires. Our contribution is connecting visible detection to evidence, human review, and a run-specific handoff.” |

At 10–25 seconds, add the sentence that matches the actual analysis mode:

- **Fixture:** “The analysis is a labeled test fixture today; it demonstrates the workflow, and real model validation is still pending.”
- **Cached genuine inference:** “These observations are saved from an actual model run on these frames; this replay makes no new inference calls.”
- **Fresh genuine inference:** “This run is analyzing the sampled frames now.” Use only when fresh inference actually occurs.
- **Unavailable:** “Analysis is unavailable for this configuration.” Do not narrate fixture observations as fresh analysis.

If the judge asks about efficiency, select the obstruction clip: “The shadow gate would skip four of six two-second windows against an always-sample baseline. These are hypothetical avoided requests; it has not skipped actual paid calls, and incident recall is not yet measured.” For the person clip it skips zero of six because person presence is deliberately conservative. Never present the zero/positive counter as a classifier accuracy score.

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
