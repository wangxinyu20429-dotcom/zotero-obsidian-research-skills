# OpenAlex search and OA PDF route

## Configuration boundary

OpenAlex is one discovery source, not a substitute for independent ranking evidence or final Zotero verification.

- Create an OpenAlex account and copy the key from <https://openalex.org/settings/api>.
- Store it only as the user-level `OPENALEX_API_KEY` environment variable or in an approved secret store.
- Never ask the user to paste a key into a Codex conversation. Never put it in a command, candidate file, URL saved to disk, log, error message, or Git.
- Restart Codex after changing a persistent environment variable so new child processes inherit it.
- Verify authentication with the official free rate-limit endpoint without printing its response key. See <https://developers.openalex.org/api-reference/authentication>.

OpenAlex pricing and limits can change. Check the official authentication page before a large run. Search calls draw from the account budget; cached content downloads currently have a per-file charge. Direct OA URLs and the cached content API are different routes.

## Search

Run a small discovery batch and require the local Zotero duplicate check:

```powershell
python scripts/openalex_import.py search `
  --query '("streamflow forecasting" AND (LSTM OR "transfer learning"))' `
  --batch-dir "<batch-dir>" `
  --year-from 2018 `
  --oa-only `
  --max-results 50 `
  --zotero-check
```

The script uses the OpenAlex Works API, filters retracted and paratext records, paginates with `per_page=100`, and writes:

- `openalex_candidates.json`: candidate records compatible with `zotero_dedup.py` and the Connector importer;
- `openalex_candidates.jsonl`: acquisition metadata used by the PDF downloader;
- `openalex_duplicates.csv`: duplicates within the OpenAlex result set;
- `openalex_search_run.json`: exact query, filters, sort, counts, API-reported cost/rate data, and request signature.

The script deduplicates by normalized DOI, then title + year + first author. OpenAlex citation count and search rank are context only. Do not label a venue as SCI/SCIE, top-tier, or high-impact without separate current evidence.

Identical reruns return `unchanged`; conflicting reruns stop rather than overwrite the batch.

## Required Zotero audit and review

The OpenAlex read-only comparison is an early guard, not the final audit. Run the standard audit on the compatible candidate file:

```powershell
python scripts/zotero_dedup.py audit `
  --candidates "<batch-dir>/openalex_candidates.json" `
  --target-collection "<target collection>" `
  --output "<batch-dir>/zotero_audit.json"
```

Review every candidate and assign a proposed action. Reuse exact Zotero matches; do not download or import another copy. Resolve ambiguous identifiers before any write. Select a small approved set by OpenAlex work ID for acquisition.

## Lawful OA PDF retrieval

Download only item-level approved records to a staging directory outside Obsidian and outside Zotero storage:

```powershell
python scripts/openalex_import.py download `
  --candidates "<batch-dir>/openalex_candidates.jsonl" `
  --pdf-dir "<external staging directory>" `
  --vault-root "<Obsidian vault root>" `
  --openalex-id W1234567890 `
  --openalex-id W9876543210 `
  --max-files 2
```

The default route accepts only a direct PDF URL from an OpenAlex OA location. It rejects candidates that were not checked against Zotero, skips existing Zotero matches, rejects private/local hosts, validates redirects, enforces a size limit, requires `%PDF-`, computes SHA-256, and writes `openalex_pdf_manifest.csv` beside the batch.

Never bypass paywalls, login requirements, CAPTCHAs, institutional restrictions, robots rules, or publisher controls. A URL does not grant redistribution rights. Preserve license, version, source, checksum, and rights notes.

### Paid cached-content fallback

The OpenAlex cached content endpoint is disabled by default. Enable it only after the user explicitly accepts the current official per-file price and a maximum file count:

```powershell
python scripts/openalex_import.py download `
  --candidates "<batch-dir>/openalex_candidates.jsonl" `
  --pdf-dir "<external staging directory>" `
  --openalex-id W1234567890 `
  --direct-or-content `
  --accept-openalex-content-cost `
  --max-files 1
```

Check <https://developers.openalex.org/download/full-text-pdfs> immediately before enabling this route. Payment to OpenAlex does not change the paper's copyright or license.

## Zotero import and verification

For unique papers, prefer Zotero Connector on the verified landing page. If Connector capture fails, use the existing guarded importer with the compatible single-candidate JSON and the verified staged PDF. For an exact existing item, reuse and file it; attach a missing PDF only through the explicitly authorized reconciliation workflow.

Do not delete staging files or report `Saved` until Zotero is reread and the correct top-level item, target collection, and readable child PDF are verified. Rerun the final duplicate audit.
