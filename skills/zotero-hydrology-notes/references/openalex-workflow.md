# OpenAlex discovery and lawful OA PDF workflow

## Purpose and authority boundary

Use OpenAlex as an external discovery index and as a locator for open-access full text. It is not the final bibliographic authority after import: the verified Zotero top-level item, its collection membership, and its child attachment are authoritative for later profiling and deep reading.

This module does not classify papers into themes, create a theme map, maintain paper-theme relations, generate problem clusters, or produce paper ideas.

## Current OpenAlex requirements

- OpenAlex API requests require an API key. Obtain and manage it according to the official authentication guide: <https://developers.openalex.org/api-reference/authentication>.
- Use the Works API search and filters documented at <https://developers.openalex.org/api-reference/works/list-works> and <https://developers.openalex.org/guides/searching>.
- Store the key only in the `OPENALEX_API_KEY` environment variable or an approved secret store. Never write it to this skill, an Obsidian note, a batch record, a run log, a URL saved to disk, or a command transcript.
- OpenAlex reports API cost and rate-limit information in its response metadata. Preserve those reported values in the run record without estimating an unreported charge.
- OpenAlex's content endpoint currently charges per PDF and does not change the original work's copyright or license. Review the current official terms before use: <https://developers.openalex.org/download/full-text-pdfs>.

Because these policies and prices can change, verify the official documentation before changing defaults or enabling a paid route.

## 1. Search and create the candidate list

Prefer an explicit Boolean or phrase query and record all filters. A typical OA search is:

Set `OPENALEX_API_KEY` in the local shell or approved secret store before the task starts; do not paste the key into a Codex conversation.

```powershell
python scripts/openalex_oa.py search `
  --query '("streamflow forecasting" AND (LSTM OR "transfer learning"))' `
  --batch-dir "<vault-root>/10_文献知识/sources/openalex/<batch-id>" `
  --year-from 2018 `
  --oa-only `
  --max-results 50 `
  --zotero-check
```

The script adds non-retracted, non-paratext, article defaults unless the operator explicitly changes the work type. It uses cursor pagination, keeps the raw OpenAlex work identifier, and records query, filters, sort, retrieval time, candidate counts, duplicate counts, cost, and rate-limit fields.

Search outputs are separate records:

- `openalex_candidates.jsonl`: one compact candidate per line, including identity, OA source, license/version when supplied, direct-PDF availability, Zotero match status, and rights note;
- `openalex_duplicates.csv`: within-result and Zotero duplicate decisions;
- `openalex_search_run.json`: query, filters, counts, request signature, API-reported cost/rate information, and tool version.

The API key and PDF binary are never included in these records. Identical reruns return `unchanged`; a different request must not overwrite an existing batch directory.

## 2. Mandatory pre-download review

Review the entire candidate list before acquisition:

1. Deduplicate by normalized DOI, then normalized title + year + first author.
2. Run the read-only Zotero comparison. If an item exists, reuse its top-level key and collection route rather than downloading or importing a second copy.
3. Exclude retracted, paratext, irrelevant, clearly wrong-version, or unresolved-identity records.
4. Confirm that the chosen location is open access and that the PDF source, version, and available license are recorded.
5. Choose a small, justified acquisition set. OpenAlex relevance, citation counts, and journal reputation are screening context, not evidence of scientific quality and not a core-paper gate.

If the Zotero local API is unavailable, `--zotero-check` must fail closed. `--allow-unchecked` is reserved for a documented exceptional run; any resulting PDF must not be imported until Zotero deduplication is completed.

## 3. Download only lawful OA PDFs to external staging

```powershell
python scripts/openalex_oa.py download `
  --candidates "<batch-dir>/openalex_candidates.jsonl" `
  --pdf-dir "<external-staging-dir>" `
  --vault-root "<vault-root>" `
  --openalex-id W1234567890 `
  --max-files 1
```

The default route accepts only a direct OA PDF URL supplied through an OpenAlex OA location. It:

- requires an explicit repeated `--openalex-id` allowlist from the reviewed candidate list;
- rejects a staging directory inside the Obsidian vault;
- rejects private/local hosts and checks every redirect;
- enforces a configurable maximum size;
- accepts a file only when the body starts with the PDF signature `%PDF-`;
- computes SHA-256 and avoids conflicting overwrites;
- writes `openalex_pdf_manifest.csv` beside the candidate records, storing the staged filename rather than copying the PDF into the vault;
- records skipped duplicates, missing direct URLs, failures, license/version/source values, checksum, and a rights note.

Never bypass a paywall, login, CAPTCHA, institutional-access restriction, robots rule, or publisher download control. The existence of a URL does not authorize redistribution.

### Paid OpenAlex content fallback

OpenAlex may expose cached content at `https://content.openalex.org/works/{work_id}.pdf`. This route is disabled by default. Use it only when all of the following are true:

- the user explicitly approves the current per-file charge and maximum file count;
- the official cost and copyright documentation was rechecked;
- `--direct-or-content` and `--accept-openalex-content-cost` are both present;
- the API key is supplied through the environment;
- the manifest records `openalex_content` as the channel.

Do not treat payment to OpenAlex as a copyright license.

## 4. Import and verify in Zotero

Import is a separate write operation and requires the user's explicit authorization.

1. For a unique paper, prefer Zotero Connector on the verified landing page so Zotero captures publisher/repository metadata and attachments together.
2. If Connector capture fails, import a verified RIS/BibTeX record with the Zotero helper, then attach the verified local PDF. Do not invent missing metadata.
3. For a duplicate, reuse the existing top-level item and add it to the requested collection. Attach the PDF only when the existing item lacks the intended attachment and the user authorized that repair.
4. Re-query Zotero and verify title, DOI or fallback identity, year, target collection, and a child PDF attachment that belongs to the same paper.
5. Only after verification may a staged file be removed. Until then, report it as staged, not as attached.
6. Feed only verified Zotero item keys to `profile_pipeline.py collect-zotero`.

An attached PDF proves availability, not that the full paper was read. Access and review levels must still follow the profile and deep-reading evidence rules.

## 5. Failure and rights handling

Record every failed or skipped item with stage, identifier, source URL host, reason, action, and retry state. Examples include API authentication failure, rate limiting, unresolved identity, Zotero unavailability, duplicate found, missing OA URL, unsafe redirect, size limit, non-PDF body, checksum conflict, and Zotero attachment verification failure.

Keep only short evidence and metadata in Obsidian. Do not commit API keys, copyrighted PDF files, authentication cookies, browser profiles, or temporary download bundles to Git.
