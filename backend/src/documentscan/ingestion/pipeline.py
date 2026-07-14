"""
SmartMatch AI -- end-to-end demo pipeline.

    Invoice (unstructured) --> line items --> semantic match against PO index
        --> rule-based reasoning layer --> OK_TO_PAY / REVIEW_FLAG / NO_MATCH / NEEDS_LLM_REVIEW

Run: python3 pipeline.py
"""

from mock_data import PURCHASE_ORDERS, INVOICES
from matcher import POIndex, match_invoice_to_pos
from reasoning import evaluate, llm_prompt_for

STATUS_ICON = {
    "OK_TO_PAY": "\033[92mOK_TO_PAY\033[0m",
    "REVIEW_FLAG": "\033[91mREVIEW_FLAG\033[0m",
    "NO_MATCH": "\033[93mNO_MATCH\033[0m",
    "NEEDS_LLM_REVIEW": "\033[96mNEEDS_LLM_REVIEW\033[0m",
}


def run():
    index = POIndex(PURCHASE_ORDERS)

    for invoice in INVOICES:
        print(f"\n{'=' * 70}\nInvoice {invoice['invoice_id']}  ({invoice['vendor']})\n{'=' * 70}")
        matches = match_invoice_to_pos(invoice, PURCHASE_ORDERS, index)

        for match in matches:
            decision = evaluate(match)
            print(f"\n  Invoice line: \"{decision.invoice_line['description']}\"")
            print(f"    qty={decision.invoice_line['qty']}  unit_price=${decision.invoice_line['unit_price']:.2f}")

            if decision.po_line:
                print(f"  Matched PO:   {decision.po_line['po_number']} line {decision.po_line['line_no']} "
                      f"-> \"{decision.po_line['description']}\"  (similarity={decision.similarity:.2f})")
            else:
                print("  Matched PO:   -- none above threshold --")

            print(f"  Decision:     {STATUS_ICON[decision.status]}  -- {decision.reason}")

            if decision.status == "NEEDS_LLM_REVIEW":
                print("  [LLM prompt that would be sent for this line]")
                print("  " + llm_prompt_for(decision).replace("\n", "\n  "))


if __name__ == "__main__":
    run()
