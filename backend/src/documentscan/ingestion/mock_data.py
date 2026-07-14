"""
Mock enterprise data: Purchase Orders (as if pulled from an ERP) and
unstructured Invoices (as if just OCR'd/parsed from a PDF).

Deliberately messy: vendors abbreviate, reorder words, use their own SKUs,
and totals don't always line up (tax, rounding, unlisted VAT).
"""

PURCHASE_ORDERS = [
    {"po_number": "PO-1001", "line_no": 1, "description": "Apple MacBook Pro 16-inch M3 Laptop",
     "qty": 10, "unit_price": 2499.00, "currency": "USD"},
    {"po_number": "PO-1001", "line_no": 2, "description": "Dell UltraSharp 27-inch 4K Monitor",
     "qty": 10, "unit_price": 549.00, "currency": "USD"},
    {"po_number": "PO-1002", "line_no": 1, "description": "Ergonomic Mesh Office Chair - Black",
     "qty": 25, "unit_price": 189.99, "currency": "USD"},
    {"po_number": "PO-1003", "line_no": 1, "description": "Annual SaaS License - Slack Enterprise Grid",
     "qty": 1, "unit_price": 84000.00, "currency": "USD"},
    {"po_number": "PO-1003", "line_no": 2, "description": "Professional Services - Slack Onboarding",
     "qty": 40, "unit_price": 175.00, "currency": "USD"},
]

INVOICES = [
    {
        "invoice_id": "INV-9001",
        "vendor": "Apple Business Sales",
        "lines": [
            {"description": "10x High-Perf Developer Laptops (MBP16 M3)", "qty": 10, "unit_price": 2499.00},
            {"description": "Dell 27in 4K Monitors", "qty": 10, "unit_price": 549.00},
        ],
    },
    {
        "invoice_id": "INV-9002",
        "vendor": "OfficeComfort Supply Co",
        "lines": [
            # price differs slightly -- looks like an unlisted regional tax
            {"description": "Mesh Task Chair, Black, Ergonomic", "qty": 25, "unit_price": 199.49},
        ],
    },
    {
        "invoice_id": "INV-9003",
        "vendor": "Slack Technologies LLC",
        "lines": [
            {"description": "Slack Enterprise Grid - Annual Subscription", "qty": 1, "unit_price": 84000.00},
            # qty mismatch: invoice says 45 hours, PO only approved 40
            {"description": "Onboarding & Implementation Services", "qty": 45, "unit_price": 175.00},
        ],
    },
    {
        "invoice_id": "INV-9004",
        "vendor": "Random Vendor Inc",
        "lines": [
            # nothing like this exists on any PO -- should be flagged as no match
            {"description": "Bulk Order of Standing Desk Converters", "qty": 15, "unit_price": 249.00},
        ],
    },
]
