---
name: supplier-invoice-total
description: Computes how much was paid to a given supplier, for all time or for a specific date range or quarter, from the Supplier Invoices knowledge base.
---

# Supplier Invoice Total

Answers "how much did we pay <supplier>" questions, for the whole relationship
or for a specific quarter/date range, by calling the `calculate_supplier_total`
tool rather than adding amounts by hand. It does not read or interpret invoice
line items, taxes, or anything other than the Gesamtbetrag (grand total) field,
and it only covers suppliers whose invoices are in the Supplier Invoices
knowledge base. It depends on the `calculate_supplier_total` tool being enabled
on this model.

## When to Use

- "How much did we pay <supplier> in 2026?"
- "What's our total spend with <supplier>?"
- "How much did <supplier> invoice us in Q2 2026?" / "... last quarter?"
- "Total for <supplier> between <date> and <date>."

## Prerequisites

- The `calculate_supplier_total` tool must be enabled on this model.
- The target supplier's invoices must already be in the Supplier Invoices
  knowledge base (uploaded and successfully processed, not stuck in a failed
  extraction state).

## How to Run

Call `calculate_supplier_total` with the supplier's full name and, for a
period-limited question, a `date_from`/`date_to` range. Never total a
sub-period yourself by picking lines out of a full-company result — call the
tool again with the narrower date range instead, so the sum stays exact.

## Quick Reference

Quarter → date range (use the year the user means):

| Quarter | date_from     | date_to       |
|---------|---------------|---------------|
| Q1      | YYYY-01-01    | YYYY-03-31    |
| Q2      | YYYY-04-01    | YYYY-06-30    |
| Q3      | YYYY-07-01    | YYYY-09-30    |
| Q4      | YYYY-10-01    | YYYY-12-31    |

Tool signature: `calculate_supplier_total(supplier_name, date_from="", date_to="")`
— omit both dates for an all-time total.

## Procedure

1. Identify the supplier's full legal name exactly as it appears on its
   invoices (e.g. "Nordlicht Facility Services GmbH"), not an abbreviation or
   partial name — the tool matches on this text. If unsure, search the
   knowledge base for the name the user gave before calling the tool.
2. If the question names a quarter or relative period ("last quarter", "Q3"),
   resolve it to an explicit `date_from`/`date_to` pair using the table above.
   For "this year"/"in 2026", use `date_from=2026-01-01`, `date_to=2026-12-31`.
   For an unrestricted, all-time question, leave both empty.
3. Call `calculate_supplier_total(supplier_name=..., date_from=..., date_to=...)`.
4. Present the tool's returned per-document breakdown and total to the user
   as-is. Do not recompute, round, or re-sum any part of it yourself.
5. If the tool's response includes a note about documents with an unreadable
   Gesamtbetrag or an unparsed date, surface that note to the user rather than
   silently dropping it — it means the total may be incomplete.

## Pitfalls

- Do not add up the breakdown lines yourself "to double-check" — if you
  disagree with the tool's total, call it again rather than overriding it;
  the whole point of this tool is that its arithmetic, not the model's, is
  trusted.
- Partial or informal supplier names (e.g. "Nordlicht" instead of "Nordlicht
  Facility Services GmbH") may still match correctly since the tool does a
  substring search, but prefer the full name when you know it to avoid
  accidentally matching an unrelated document that happens to share a word.
- Credit notes are already stored as negative amounts and are included
  automatically — do not look them up separately or subtract them again.
- A supplier with zero results is not necessarily an error: it may genuinely
  have no invoices in the selected period, or its invoice(s) may have failed
  OCR/text extraction and need re-processing in the knowledge base first.

## Verification

Ask: "How much did we pay Nordlicht Facility Services GmbH in Q3 2026?" — it
should call the tool with `date_from=2026-07-01`, `date_to=2026-09-30`, and
the result should include both RE-2026-0417 (3.058,30 €) and the GS-2026-0021
credit note (-285,60 €), netting to 2.772,70 €.
