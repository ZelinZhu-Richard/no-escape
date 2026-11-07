# Small development evaluation

The labeling page stores human submissions only. Initial state is **awaiting labels**. The agent-reviewed demo scenario and fixture analysis are not human ground truth or measured model performance.

With the operator running, export the submitted labels and generate a pending report:

```sh
python3 clearway/scripts/evaluate.py
```

Reports are ignored at `clearway/data/evaluation/report.json`. Without genuine predictions the report stays pending; it never invents detections or treats missing predictions as normal traffic.

To evaluate a frozen set, provide JSON files:

```sh
python3 clearway/scripts/evaluate.py --labels clearway/data/evaluation/labels.json --predictions clearway/data/evaluation/predictions.json
```

Labels are an array (or `{ "labels": [...] }`) with the API's saved `id`, `source_id`, `start_seconds`, `end_seconds`, `label`, and `reviewer`. Predictions are an array (or `{ "predictions": [...] }`) with:

- `label_id`: exactly one prediction per labeled interval.
- `status`: `complete` or `unavailable`.
- `predicted_category`: `normal`, `road_obstruction`, `queue`, or `uncertain`.
- `analysis_mode`: `fresh`, `cached`, or `fixture`.
- `provenance_id`: the genuine result/cache identifier. A label string is not proof of provenance; retain and review the matching analysis ledger/result.
- Optional `latency_ms` and actual/explicitly estimated `cost_usd`. Missing costs remain unknown.
- For independent local-gate evaluation: `gate_passed` boolean, `gate_mode: "local"`, and `gate_provenance_id` linked to the recorded gate run. Gate-blocked intervals still need this record with `status: "skipped"`, even though no VLM prediction exists. Synthetic gate decisions use `gate_mode: "fixture"` and are excluded from measured gate counts.

Freeze the code revision, model/prompt/schema, preprocessing, selected intervals, and any gate thresholds before creating the prediction file. Retain these in a local evaluation manifest alongside raw results. Do not tune on final evaluation scenes. If all scenes were used in development, present **development results** only.

The script excludes fixtures, unavailable/missing predictions, and uncertain human labels from automatic accuracy counts, and reports their counts separately. It reports normal-scene false alerts, obstruction detections, gate coverage and hypothetical requests avoided, latency median/max/n by mode, and costs with missing-cost coverage. Gate savings are not a billable-savings claim. One source with many windows remains one scene, not many independent incidents. These clips do not establish natural-scene recall or incident onset delay.

Gate metrics are computed separately from completed VLM predictions. Suppressed positive windows remain in the gate denominator; otherwise the gate's misses would disappear and its coverage would be overstated.

`tests/test_evaluation.py` uses synthetic test records in memory; none is added to the application's human-label database.
