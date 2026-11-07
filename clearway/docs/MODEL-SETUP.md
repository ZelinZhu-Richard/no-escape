# Real Gemini validation

The user authorized **up to $5 total** for this validation on November 7, 2026. The application also enforces **at most five inference attempts** across its persistent local ledger. This replaces the overnight $0 Gemini limit for this bounded follow-up only. Claude and OpenAI remain disabled.

## Teammate setup

Create or edit **`clearway/.env` on the machine running Clearway**, with:

```dotenv
GEMINI_API_KEY=YOUR_PRIVATE_GEMINI_API_KEY
```

Use a Gemini Developer API key for the intended project. Do not put it in `web/.env`, a `VITE_` variable, a chat, a command argument, or Git. The backend automatically loads the ignored `clearway/.env` file. Existing process environment variables take precedence; values are read literally, without shell execution or variable interpolation. `clearway/.env.example` contains only public setup placeholders.

The selected defaults are `GEMINI_MODEL=gemini-3.5-flash-lite` and `GEMINI_MODEL_VERSION=gemini-3.5-flash-lite`. The [official model page](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite) documents a stable model supporting image inputs and structured output. No model/provider substitution occurs on failure. A returned version must match the configured pin before its response is cached.

From the repository root:

```sh
make gemini-check       # Offline presence/prerequisite check; never reveals the key
make gemini-smoke       # Read-only model-access check, one fresh analysis if needed, then genuine-cache replay
make gemini-replay      # Frozen cache only: no credential probe or inference call
```

The smoke command extracts real frames at **1, 4, and 8 seconds** from the licensed obstruction clip. It sends those frames to Gemini with the road-observation schema, saves validated provider provenance, and verifies that repeating the result from cache makes no further inference calls. It does not submit human labels or confirm an incident. A valid no-candidate response stays a no-candidate response.

Successful output is saved locally in `clearway/data/inference/road-obstruction-validation.json`. Compare its observations with the video before presenting it. A schema-valid response is not an accuracy measurement. `make gemini-replay` requires the exact matching footage/model/prompt/configuration; a fixture cannot satisfy the cache.

## Use the result in the interface

After the key is added, restart the running `make serve` process so the backend loads it. Refresh the console at `http://127.0.0.1:8000`.

- Select **Fresh inference** and start the obstruction replay to use the configured adapter. If a matching genuine result was already saved by the smoke command, its badge correctly says **Cached model result**.
- For repeated expo runs, select **Frozen model cache**. It makes no network inference calls, even on a miss. Reset and replay preserve that selection.
- The existing fixture walkthrough remains available and visibly labeled. Human confirmation and simulated map placement remain separate from the model result.

The fresh option is enabled only when local credential, model, authorization, and remaining-budget checks pass. This readiness check does not claim that Google has accepted the key or that account billing works.

## Budget and account scope

This is the **Gemini Developer API**, not Vertex AI. A Google Cloud billing credit has not been verified for this endpoint. The approved $5 permits bounded billed usage without assuming credits apply.

The ignored `clearway/data/gemini-budget-authorization.json` on this machine records the user's approval, fixed model/version, $5 ceiling, five-attempt ceiling, and a maximum 24-hour validity window. The implementation validates that record; merely supplying a key does not authorize spend. A fresh checkout does not contain the authorization or ledger. Do not duplicate the authorization across machines or delete the ledger to replenish the shared task budget.

For the selected model, the [published standard rates](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite), checked November 7, are $0.30 per million input tokens and $2.50 per million output tokens, including thinking. Each attempt reserves **$0.50** before transport, conservatively covering the model's full documented input/output limits at these rates. The request uses one candidate, minimal thinking, a 4,096-token output limit, and no paid tools/grounding. Failed attempts and timeouts retain their reservation; no automatic retry runs.

The ledger separates reserved budget, usage-derived cost estimates, and unknown charges. It prices reported prompt tokens plus candidate/thinking tokens once. Missing or inconsistent usage stays unknown; a reservation remains as the cost bound. Estimates are not billing receipts and do not include another application using the same project/key. Google billing is the source of truth for actual charges.

The earlier verified-zero-charge record remains supported for the original route, but it is not needed for this user-authorized paid validation. Invalid/expired paid authorization fails closed. Renewing a record does not reset the persistent request count or reservations.

## If the check fails

- **Key missing:** add it to the backend's local `.env`; no request is made until it exists.
- **Authentication/permission:** verify the correct Gemini key and project access. Raw provider errors and credentials are never printed.
- **Quota/rate limit:** check the project's quota and billing. The app does not retry or switch providers.
- **Model/version or structured-output mismatch:** inspect the sanitized failure, verify the model configuration, and fix the adapter before another bounded attempt. Do not copy fixture observations into the genuine cache.
- **Expired/exhausted authorization:** use existing frozen results. Review authorization and the ledger before any new call.

Local cache and ledger: `data/analysis-cache/` and `data/spend-ledger.jsonl`. Keep them ignored. Cache identity includes frame bytes/times, provider/model/version, prompt/schema, generation configuration, preprocessing, and context. The model-access preflight sends no footage and generates no content; generation request counts are reported separately.
