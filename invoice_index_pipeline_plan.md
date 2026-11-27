# Plan: structured invoice index (replace vector search + regex for arithmetic)

## Problem with the current `calculate_supplier_total`

- Uses `query_doc` (top-k ANN similarity search, `TOP_K=50`) to find "all invoices
  for supplier X". Similarity search is probabilistic, not exhaustive - it can
  silently under-return once a supplier has enough invoices or a chunk just
  doesn't rank in the top K. This recreates the original ticket's bug ("the
  number is too low") one layer down.
- Parses amounts/dates with regex against OCR'd markdown chunks, re-done on
  every query, and silently `continue`s past anything that doesn't match -
  a malformed invoice just vanishes from the sum instead of raising.

Verified against the running `open-webui` image (`ghcr.io/open-webui/open-webui:main`,
local container `open-webui`) that better primitives already exist:

- `Knowledges.get_files_by_id(knowledge_id)` - a plain SQL join, returns every
  `FileModel` in a knowledge base. Exhaustive, not ranked - nothing can fail to
  show up.
- `FileModel.data['content']` - the full extracted text for that file, stored
  once at ingestion (what Mistral OCR produced), independent of chunking.
- `VECTOR_DB_CLIENT.get(collection_name)` (Chroma) - a true full-collection
  fetch with no top-k, for completeness if chunk-level data is ever needed.

## Design

1. Leave file upload, OCR extraction, chunking and embedding exactly as is -
   that stays the semantic-search/citations layer for conversational Q&A.

2. New Tool: `rebuild_invoice_index` (Workspace -> Tools, same mechanism as
   the existing tool, same `__request__.app.state` access):
   - `files = await Knowledges.get_files_by_id(KNOWLEDGE_ID)`.
   - For each file: `text = file.data.get('content', '')` - one clean
     full-document string, no chunk reassembly.
   - Extract `{supplier, invoice_number, date, gesamtbetrag, is_credit_note}`
     from that text.
   - Any required field missing -> raise, and record that filename as
     `extraction_failed` instead of silently dropping it. Fails loud right
     after upload, when it's cheap to notice and fix - not silently at query
     time when an accountant is trusting the number.
   - Write validated rows to `./data/invoice_index.sqlite3` (the `./data`
     volume is already mounted in `docker-compose.yml`). Build into a temp
     file and rename over the old one, so a failed run can't leave a
     half-written index in place.

3. Rewrite `calculate_supplier_total`: delete `query_doc`, `EMBEDDING_FUNCTION`
   and all regex. It becomes: open `invoice_index.sqlite3`, filter by supplier
   + date range, sum in Python. Deterministic, nothing left to be fragile
   about.

4. Trigger: Open WebUI has no native "on file added to knowledge base" hook
   exposed to Tools/Functions. Options:
   - (a) Admin runs `rebuild_invoice_index` conversationally right after
     uploading/reprocessing invoices - fits the existing workflow, one-line ask.
   - (b) A cron on the EC2 host calling Open WebUI's REST API with an admin
     key to do it unattended.
   Plan: ship (a) given the time left; (b) only if time remains.

## Status

Not implemented yet - this is the plan to build if/when picked up.
