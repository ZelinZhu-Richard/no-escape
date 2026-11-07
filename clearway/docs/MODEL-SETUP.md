# Model access after the overnight build

Default operation is fixture-only or frozen cached replay, with **zero billable Gemini usage** permitted. No credentials, billing verification, or model ID have been supplied. This build does not silently switch to Claude or OpenAI.

The implemented transport is the **Gemini Developer API**, using [generateContent](https://ai.google.dev/api/generate-content). It is not a Vertex AI transport. A Google Cloud billing credit is not proof of eligibility for this endpoint. If the credit requires Vertex, the morning implementation must add and verify that route explicitly.

## Current configuration

The operator process reads:

- `GEMINI_API_KEY`: Developer API credential. Keep it private.
- `GEMINI_MODEL`: exact supported model ID, no default.
- `GEMINI_MODEL_VERSION`: expected returned model version, no default.

Fresh calls additionally require `clearway/data/gemini-zero-charge-verification.json` (or the configured data directory). This local file records a human's actual billing verification; copying the shape below does **not** establish free access:

```json
{
  "provider": "gemini-developer-api",
  "api_base": "https://generativelanguage.googleapis.com/v1beta/models",
  "model": "REPLACE_WITH_VERIFIED_MODEL",
  "model_version": "REPLACE_WITH_VERIFIED_VERSION",
  "allow_zero_charge_calls": true,
  "billable_cost_upper_bound_usd": 0,
  "max_requests": 10,
  "verified_by": "PERSON_WHO_CHECKED_BILLING",
  "evidence_reference": "ACTUAL_ACCOUNT_AND_ENDPOINT_EVIDENCE",
  "verified_at": "REPLACE_WITH_UTC_TIMESTAMP",
  "expires_at": "REPLACE_WITH_UTC_TIMESTAMP"
}
```

The record must match the configured endpoint/model/version, be currently valid, and span at most 24 hours. The global request ledger limits this adapter to at most ten attempted requests; there are no automatic retries. Validation remains active under optimized Python. Do not fill this file with invented evidence just to unlock the adapter.

**If only paid access is available:** keep analysis unavailable/fixture under the current cap. A user-authorized nonzero cap requires an explicit adapter/price-reservation policy change; this prototype intentionally does not enable paid requests merely by exporting a budget variable. Record the chosen endpoint, verified prices, cap, and eligibility before changing that boundary.

## What a genuine request does

Extract three real JPEG frames with ffmpeg at 1, 4, and 8 seconds. Submit them with a road-observation prompt and structured-output schema. Validate returned timestamps, fields, and model version; save genuine provider response provenance. The prompt does not provide the expected incident label and does not treat text inside footage as instructions.

The cache identity includes the actual ordered frame bytes/times, provider/model/version, prompt, schema, preprocessing version, and relevant source context. A genuine cached replay needs matching model/version configuration and footage, but no API key or active billing record. It never makes network requests on a miss.

The ledger lives at `data/spend-ledger.jsonl`; genuine cache entries live at `data/analysis-cache/`. Unknown/corrupt telemetry is shown as unavailable rather than zero. Fixture runs are logged distinctly and cannot be promoted to genuine inference by saving or replaying them. Keep these files private and ignored in Git.

Real model behavior and account billing remain morning validation tasks. Stubbed transport tests validate code paths and limits, not real-world detection accuracy.
