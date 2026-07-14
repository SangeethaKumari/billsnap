# SmartMatch AI — Invoice-to-PO Semantic Reconciler

A small, self-contained pipeline that mirrors the core problem in AP automation:
matching messy, human-written invoice line items to structured PO records, and
deciding — with a mix of rules and (optionally) an LLM — whether a line is safe to pay.

## Run it
```
python3 pipeline.py
```
No API keys, no downloads. Everything runs offline in seconds.

## Architecture
```
Invoice (unstructured) --> line items --> semantic match against PO index (TF-IDF/cosine)
    --> rule-based reasoning layer --> OK_TO_PAY / REVIEW_FLAG / NO_MATCH / NEEDS_LLM_REVIEW
                                              |
                                   (ambiguous cases only)
                                              v
                                   LLM prompt template (reasoning.llm_prompt_for)
```

- `mock_data.py` — fake ERP POs + fake OCR'd invoices, deliberately messy (abbreviations, reordered words, vendor-specific SKUs, one legit price variance, one qty overage, one line with no PO at all).
- `matcher.py` — the "vector index." Uses TF-IDF + cosine similarity so it runs with zero network access. The interface is identical to a real embeddings backend — see the comment in `POIndex._embed_text` for exactly where you'd swap in `sentence-transformers` or `text-embedding-3-small` against a real vector DB (ChromaDB/FAISS/pgvector).
- `reasoning.py` — deterministic business rules do the volume (qty tolerance, price tolerance %). Only the genuinely ambiguous band (3–8% price variance) gets routed to an LLM prompt. That routing logic is the actual design decision worth discussing.
- `pipeline.py` — orchestrates and prints a readable audit trail per line item.

## Why it's built this way (say this in the interview)

**1. "I didn't just wire up an LLM to do everything."**
Most invoice lines are boring — they match cleanly and the price is right. Running every line through an LLM is slow and expensive at enterprise volume. The pipeline uses cheap deterministic rules for the ~85-90% of clean cases and only escalates the ambiguous tail to a model. This is the cost/latency answer a Director of Engineering wants to hear.

**2. "The matching layer is decoupled from the embedding model."**
`POIndex` exposes a `best_match(text) -> (po_line, score)` interface. Whether that's backed by TF-IDF, sentence-transformers, or a hosted embeddings API is an implementation detail behind that one class. In a real AP product the embedding model *will* change over the years — the system shouldn't have to be rebuilt when it does.

**3. "I picked a threshold-based match, not exact string match, on purpose."**
Vendors never write item descriptions the way your ERP does. The similarity threshold is a tunable business parameter, not a hardcoded assumption — worth asking AppZen how *they* tune it (this is a great question to turn back on the interviewer, see below).

**4. "Every decision carries a reason, not just a status."**
`Decision.reason` is a human-readable audit line. In compliance-heavy finance software, an unexplained "flagged" status is nearly useless to the AP team that has to act on it.

## What I'd add for production (be upfront about this — it shows judgment)
- Real extraction: LayoutLMv3 or a document-AI API for spatial/tabular extraction instead of assuming clean line items already exist.
- A real vector DB (ChromaDB/pgvector) instead of an in-memory TF-IDF matrix, for scale and incremental indexing as POs are created.
- A live LLM call (Claude, small model) for the `NEEDS_LLM_REVIEW` band, with the prompt template already sketched in `reasoning.llm_prompt_for`.
- Feedback loop: when a human AP reviewer overrides a decision, log it and use it to retune the similarity threshold and price-tolerance bands over time.

## Questions to ask the Director (turns the interview into a conversation, not a quiz)
- "How do you balance vector-distance thresholds against strict exact-match compliance rules — is that threshold static or learned per vendor/category?"
- "For the exception-handling layer, do you route to an LLM per-line or batch a whole invoice? How do you think about cost at your invoice volume?"
- "How do you handle drift when a vendor changes how they describe line items over time — do you re-embed, or is there a feedback signal from AP reviewers?"

## Elevator pitch (30 seconds)
"I built a small prototype called SmartMatch AI that mirrors the core problem in autonomous AP: matching messy invoice line items to PO records that don't use the same wording. It uses a semantic matching layer decoupled from the embedding model, deterministic rules for the volume of clean matches, and only escalates genuinely ambiguous price discrepancies to an LLM — because I wanted the design to reflect real cost and latency constraints, not just 'throw an LLM at it.' I'd love to hear how AppZen tunes match thresholds against strict compliance rules in production."
