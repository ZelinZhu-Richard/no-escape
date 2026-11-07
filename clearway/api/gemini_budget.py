"""Fixed-price, narrowly authorized Gemini smoke-run accounting.

Prices and full context limits checked on 2026-11-07 against:
https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite
https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
No tools, grounding, file upload, paid cache service, or provider substitution.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math

from .gemini import API_BASE

PAID_MODEL = "gemini-3.5-flash-lite"
INPUT_TOKEN_LIMIT = 1_048_576
OUTPUT_TOKEN_LIMIT = 65_536
INPUT_USD_PER_MILLION = Decimal("0.30")
OUTPUT_USD_PER_MILLION = Decimal("2.50")
RESERVATION_USD = Decimal("0.50")
MAX_AUTHORIZED_USD = Decimal("5.00")
MAX_PAID_REQUESTS = 5
PRICE_BASIS = "gemini-3.5-flash-lite-standard-usd-2026-11-07"
PRICE_REFERENCE = "https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite"


def amount(value) -> Decimal:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("A finite numeric cost is required")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid cost") from None
    if result < 0:
        raise ValueError("A negative cost is invalid")
    return result


def validate_paid_policy(policy: dict, model: str, version: str) -> dict:
    """Normalize a current user authorization; never infer it from credentials."""
    if not isinstance(policy, dict):
        raise ValueError("Invalid paid authorization")
    if (policy.get("mode") != "paid" or policy.get("provider") != "gemini-developer-api"
        or policy.get("api_base") != API_BASE or model != PAID_MODEL
        or policy.get("model") != model or policy.get("model_version") != version
        or not (version == PAID_MODEL or version.startswith(PAID_MODEL + "-"))):
        raise ValueError("Paid authorization does not match the supported route")
    cap = amount(policy.get("max_billable_usd"))
    if not 0 < cap <= MAX_AUTHORIZED_USD:
        raise ValueError("Paid authorization exceeds the approved dollar ceiling")
    limit = policy.get("max_requests")
    if type(limit) is not int or not 1 <= limit <= MAX_PAID_REQUESTS:
        raise ValueError("Paid authorization exceeds the approved request ceiling")
    for field in ("approved_by", "approval_reference"):
        if not isinstance(policy.get(field), str) or not 1 <= len(policy[field]) <= 500:
            raise ValueError("Authorization attribution is missing")
    approved = datetime.fromisoformat(policy["approved_at"])
    expires = datetime.fromisoformat(policy["expires_at"])
    now = datetime.now(timezone.utc)
    if not approved.tzinfo or not expires.tzinfo or not approved <= now < expires:
        raise ValueError("Authorization is not current")
    if (expires - approved).total_seconds() > 24 * 3600:
        raise ValueError("Authorization must be scoped to at most one day")
    return {**policy, "billing_mode": "paid", "reservation_usd": float(RESERVATION_USD),
            "budget_cap_usd": float(cap), "price_basis": PRICE_BASIS,
            "price_reference": PRICE_REFERENCE}


def estimate_usage(usage: dict) -> float | None:
    """Price reported input and output+thinking, without counting total twice.

    Missing/inconsistent token metadata is unknown cost, not zero. A missing
    thoughtsTokenCount represents a zero-valued optional protobuf field; the
    complete total must corroborate that assumption.
    """
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("promptTokenCount")
    candidates = usage.get("candidatesTokenCount")
    thoughts = usage.get("thoughtsTokenCount", 0)
    total = usage.get("totalTokenCount")
    if any(type(value) is not int or value < 0 for value in (prompt, candidates, thoughts, total)):
        return None
    if total != prompt + candidates + thoughts:
        return None
    if prompt > INPUT_TOKEN_LIMIT or candidates + thoughts > OUTPUT_TOKEN_LIMIT:
        return None
    cost = (Decimal(prompt) * INPUT_USD_PER_MILLION
            + Decimal(candidates + thoughts) * OUTPUT_USD_PER_MILLION) / Decimal(1_000_000)
    return float(cost)


def spending(rows: list[dict]) -> dict:
    """Summarize reservations separately from usage-derived cost estimates."""
    reservations = {}
    for row in rows:
        if row["event"] != "request_reserved" or row.get("provider") != "gemini-developer-api":
            continue
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or request_id in reservations:
            raise ValueError("Invalid request reservation")
        fallback = None if row.get("billing_mode") == "paid" else 0
        reserved = amount(row.get("reserved_cost_usd", row.get("estimated_billable_cost_usd", fallback)))
        reservations[request_id] = (reserved, row.get("billing_mode", "zero_charge"))
    estimates = {}
    for row in rows:
        if row["event"] != "request_succeeded" or row.get("request_id") not in reservations:
            continue
        if row.get("estimated_billable_cost_usd") is not None:
            estimates[row["request_id"]] = amount(row["estimated_billable_cost_usd"])
    reserved_total = sum((item[0] for item in reservations.values()), Decimal(0))
    known_total = Decimal(0)
    accounted_total = Decimal(0)
    unknown = 0
    for request_id, (reserved, mode) in reservations.items():
        if mode == "zero_charge":
            known = Decimal(0)
        else:
            known = estimates.get(request_id)
        if known is None:
            unknown += 1
            accounted_total += reserved
        else:
            known_total += known
            accounted_total += known
    return {
        "reserved_spend_usd": float(reserved_total),
        "estimated_spend_usd": float(accounted_total),
        "usage_estimate_usd": float(known_total),
        "estimated_billable_cost_usd": None if unknown else float(known_total),
        "unknown_cost_requests": unknown,
        "spend_basis": "usage_estimates_plus_unsettled_reservations" if unknown else "usage_estimates",
    }
