"""
Reasoning Layer: decides OK-to-Pay vs Review Flag vs No Match.

PRODUCTION NOTE:
The checks below are deterministic business rules (qty tolerance, price
tolerance %). That's intentional -- most AP discrepancies are boring and
rule-based, and rules are cheap, fast, and auditable. An LLM should only
be invoked for the residual ~10-15% of cases a rule can't confidently
resolve (see `needs_llm_review`), e.g. "price is 5.5% over PO but the
vendor's memo mentions a regional VAT change." That's the hybrid design:
cheap deterministic rules do the volume, an LLM call (Claude/GPT-4o-mini)
only fires for the ambiguous tail. This is the answer to "how do you
control LLM cost/latency at scale" -- you're not supposed to run every
line item through a model.
"""

from dataclasses import dataclass
from matcher import MatchResult

QTY_TOLERANCE = 0          # invoice qty must not exceed PO qty
PRICE_TOLERANCE_PCT = 0.03  # 3% price variance auto-approved (rounding/FX)
LLM_REVIEW_BAND_PCT = 0.08  # 3-8% over -> ambiguous, route to LLM reasoning


@dataclass
class Decision:
    invoice_line: dict
    po_line: dict | None
    similarity: float
    status: str        # "OK_TO_PAY" | "REVIEW_FLAG" | "NO_MATCH" | "NEEDS_LLM_REVIEW"
    reason: str


def evaluate(match: MatchResult) -> Decision:
    inv = match.invoice_line

    if match.status == "no_match" or match.po_line is None:
        return Decision(inv, None, match.similarity, "NO_MATCH",
                         "No PO line cleared the similarity threshold -- likely off-contract spend.")

    po = match.po_line

    if inv["qty"] > po["qty"] + QTY_TOLERANCE:
        return Decision(inv, po, match.similarity, "REVIEW_FLAG",
                         f"Invoice qty ({inv['qty']}) exceeds PO qty ({po['qty']}).")

    price_diff_pct = abs(inv["unit_price"] - po["unit_price"]) / po["unit_price"]

    if price_diff_pct <= PRICE_TOLERANCE_PCT:
        return Decision(inv, po, match.similarity, "OK_TO_PAY",
                         f"Match confidence {match.similarity:.2f}; price within {PRICE_TOLERANCE_PCT:.0%} tolerance.")

    if price_diff_pct <= LLM_REVIEW_BAND_PCT:
        return Decision(inv, po, match.similarity, "NEEDS_LLM_REVIEW",
                         f"Price is {price_diff_pct:.1%} over PO -- ambiguous band, "
                         f"route to LLM to check for tax/VAT/FX explanation before flagging.")

    return Decision(inv, po, match.similarity, "REVIEW_FLAG",
                     f"Price is {price_diff_pct:.1%} over PO -- outside auto-approve and LLM-review bands.")


def llm_prompt_for(decision: Decision) -> str:
    """This is the actual prompt you'd send to a small LLM for the
    NEEDS_LLM_REVIEW cases. Kept as a template here (no live API call in
    this offline demo) so the design is visible even without a key."""
    return f"""You are an AP compliance assistant. An invoice line item was matched to a PO line
by semantic similarity ({decision.similarity:.2f}) but the price differs from the PO.

Invoice line: {decision.invoice_line}
PO line: {decision.po_line}

Decide if this discrepancy is plausibly explained by a legitimate cause (regional VAT,
currency conversion, documented price escalation clause) versus a billing error or
overcharge. Respond with a status of OK_TO_PAY or REVIEW_FLAG and a one-sentence reason."""
