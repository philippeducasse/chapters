# Short notes

## Root cause

The admin's complaint was from a bug at the document ingestion time.

Four invoices (BB-2026-151, KWP-2026-0702, RE-2026-0417, RE-2026-0533) are scanned images, not text PDFs. Open WebUI's default extractor doesn't read text from a scanned PDF, so it marks the file as failed and never adds it to the knowledge base, even though the admin can still see it in the UI. That's why the assistant insisted RE-2026-0417 "doesn't exist"; it genuinely wasn't searchable. That's also why the sums didn't match.

## Fix

- Switched the knowledge base's content extraction engine to Mistral OCR and re-added the 4 failed files, so they get real text instead of nothing. The embeddings are different however, which adds some fragility to the knowledge base.

## Trade-offs I accepted

- Picked Mistral Large 4 over the cheaper Small model for the assistant. Query volume here is tiny, so the cost difference is nothing, and correctness matters more than speed for this exact ticket. I actually wanted to use the largest model, Mistral Large 4, but it has an annoying glitch in the COT display.
- The tool only sums per supplier, not the whole knowledge base at once. A "total everything" query still falls back to the model doing its own arithmetic - I know this is unreliable (see above) and decided it wasn't worth building given the time left.
- Left the other 16 invoices on the default (non-OCR) extractor instead of reprocessing everything through Mistral OCR. This is the right call, not a shortcut: those 16 are native text PDFs that already extract cleanly, and running OCR on them would trade a clean text-layer read for a lossier image-render-then-OCR round trip, for no benefit. The real trade-off it creates: OCR'd and native-text invoices get chunked differently (Mistral OCR's markdown splits on headers, native text doesn't), which `calculate_supplier_total` has to account for by grouping chunks per file - see the note on that tool below.
- Generated `WEBUI_SECRET_KEY` fresh on every boot instead of a durable secret store. Fine for a single demo instance, not how I'd do it for a real OpCo deployment.
- SSH is locked to my own IP in the security group rather than something more general - fine for me, would need a real access pattern (bastion, VPN) for a team.

## What I left out because of time

- `calculate_supplier_total` uses vector similarity search (top-k) to find "all invoices for a supplier," which is probabilistic, not exhaustive - it can silently under-return as the knowledge base grows, recreating the original "too low" bug one layer down. It also parses amounts/dates with regex against OCR'd markdown at query time and silently skips anything that doesn't match, instead of failing loudly. Designed a fix (structured extraction into a SQLite index at ingestion time, read deterministically at query time, raising instead of skipping on bad data) - see `invoice_index_pipeline_plan.md` - but didn't implement it given the time left.
- No automated tests for the custom tool or skill. I verified both by hand, directly against the live knowledge base, not with a test suite.
- Didn't wire the Slack connection into an actual workflow (e.g. auto-posting when a file fails extraction). It's connected and I can explain the value, but nothing calls it yet.
- Didn't fix the UI glitch for mistral large 4
- No monitoring/alerting on the instance itself (just the one EC2 box, no uptime checks).
- No CI for the Terraform - applied by hand from my machine.
- Didn't stress-test the skill against many different phrasings of the same question - tested the cases I expected an accountant to actually ask.
