---
name: zotero-literature-import
description: Search scholarly literature from a user topic or query through OpenAlex and other authoritative sources, prioritize relevant high-impact SCI/SCIE journals only with verifiable evidence, deduplicate the candidate list and the local Zotero library, retrieve item-level approved lawful OA PDFs to external staging, reuse existing Zotero items by adding them to a requested collection, import new items through Zotero Connector or a safe API path, and perform a post-import duplicate audit. Use for OpenAlex 文献检索、开放获取 PDF 抓取、literature discovery、顶刊筛选、Zotero 查重、批量入库、collection/folder filing, or requests to search and save papers into Zotero.
---

# Zotero Literature Import

Search first, audit twice, and mutate Zotero only from an explicit item-level plan. Treat a Zotero “folder” as a collection: one item can belong to multiple collections without being duplicated.

## Required routing

- Use `nature-academic-search` for multi-source discovery and ranking when available.
- Use `nature-ref-verifier` when identity or metadata conflicts need authoritative verification.
- Use `web-access` for all internet access and follow its browser-safety instructions.
- Use `zotero` to probe the local library and Connector before falling back to bundled scripts.
- Read [references/openalex-search-and-pdf.md](references/openalex-search-and-pdf.md) before OpenAlex search, API configuration, or PDF retrieval.
- Read [references/search-and-ranking.md](references/search-and-ranking.md) before searching.
- Read [references/zotero-write-policy.md](references/zotero-write-policy.md) before any Zotero mutation.
- Read [references/existing-item-pdf-reconciliation.md](references/existing-item-pdf-reconciliation.md) when an existing Zotero item lacks a PDF but Zotero Connector can capture one from the article page.
- Read [references/institutional-access.md](references/institutional-access.md) whenever a publisher PDF requires institutional authentication. Obtain the exact institution from the current user request or a private user-controlled local setting; never hard-code it in the Skill or public artifacts.

Do not send unpublished papers, private PDFs, or sensitive library data to public services without explicit permission.

## Workflow

### 1. Define the request

Extract the research question, concepts and synonyms, date/language/document-type limits, desired count, target Zotero library and collection, and whether metadata-only fallback is allowed. If count is absent, prepare at most 20 shortlisted records. If the target collection is absent, ask for it before mutation; searching can continue.

### 2. Search broadly, rank transparently

Search multiple independent academic sources. Start with DOI/indexing sources and publisher records, then add discipline databases, citation indexes, and lawful web discovery. Prefer relevance and evidential fit; use journal prestige only as a secondary ranking signal.

For an OpenAlex route, read the dedicated reference and use the bundled helper. Require `OPENALEX_API_KEY` from the process environment and never ask the user to paste it into chat:

```powershell
python scripts/openalex_import.py search `
  --query "<query>" `
  --batch-dir "<batch-dir>" `
  --oa-only --max-results 50 --zotero-check
```

Use `openalex_candidates.json` for the standard Zotero audit. Search rank and citation count are contextual signals, not proof of quality, SCI status, journal tier, or relevance.

Never invent impact factor, JCR quartile, SCI/SCIE inclusion, or “top journal” status. Record the metric/source and access date. If current authoritative evidence is inaccessible, label the ranking as a proxy such as `venue-prestige proxy`, `citation proxy`, or `domain reputation`, not as a verified impact factor.

### 3. Build a normalized candidate file

Create UTF-8 JSON using the schema in [references/search-and-ranking.md](references/search-and-ranking.md). Preserve provenance for metadata, journal evidence, and PDF access. Do not include a paper merely because its venue is prestigious.

The OpenAlex helper also keeps `openalex_candidates.jsonl` for guarded PDF acquisition and a separate run log/duplicate file. Do not merge API logs or secrets into the import candidate records.

### 4. Run the first duplicate audit

Run the bundled read-only audit before opening any save action:

```powershell
python scripts/zotero_dedup.py audit --candidates candidates.json --target-collection "目标分类路径" --output audit.json
```

Deduplicate the candidate list internally, then compare it with every top-level Zotero item. Match in this order:

1. Exact normalized DOI, PMID, PMCID, or arXiv ID.
2. Normalized title plus compatible first-author surname and year, using title-token Jaccard similarity at least 0.90.
3. Manual review for conflicting identifiers or ambiguous near-matches.

Treat a preprint and its published journal article as related versions, not automatic duplicates. Never auto-merge or delete Zotero items.

### 5. Present a dry-run manifest

Show one row per candidate with title, year, venue, venue-evidence status, identifier, PDF source/status, duplicate result, and proposed action:

- `REUSE_AND_FILE`: existing Zotero item; add its key to the target collection.
- `IMPORT_WITH_PDF`: new item with a validated lawful PDF route.
- `TEMP_CAPTURE_RECONCILE`: existing item lacks a PDF; with explicit authorization, use Connector to create a temporary capture, transfer/merge its verified PDF into the canonical item, and clean the temporary duplicate.
- `REVIEW_DUPLICATE`: ambiguous/conflicting match; no automatic write.
- `BLOCKED_NO_PDF`: no lawful accessible PDF and metadata-only import was not authorized.
- `SKIP`: irrelevant, retracted, superseded, or otherwise excluded with a reason.

Obtain item-level confirmation before external writes unless the current user explicitly requested direct execution after seeing equivalent selection criteria. Never infer permission to import an unreviewed expanded set.

### 6. Reuse existing items

Do not create a second item. Add the existing item to the requested collection:

```powershell
python scripts/zotero_webapi_collection.py add --item-key ITEMKEY --collection-key COLLECTIONKEY --yes
```

This route requires `ZOTERO_USER_ID` and a write-enabled `ZOTERO_API_KEY`, and the item must be synced. If unavailable, stop at a clear manual gate: ask the user to drag the existing item into the collection or configure the credentials. Never edit `zotero.sqlite` directly.

If multiple existing Zotero duplicates already exist, select a canonical candidate by PDF presence, metadata completeness, notes/annotations, and citation-key stability; report all keys and require review. Do not merge or delete them.

### Existing item missing a PDF

Connector capture from a publisher landing page can succeed when resolver-only download fails because the browser carries translator context, login state, and dynamically generated attachment URLs. Connector normally creates a new parent item instead of attaching to an arbitrary old item, so use the reconciliation workflow only when all of these are true:

1. The canonical existing item is an exact DOI/PMID/PMCID/arXiv match and has no readable PDF.
2. The user explicitly authorizes temporary duplicate creation plus merge/deletion in the current task.
3. The Connector target is the intended editable library/collection.
4. The temporary capture is verified to have the same persistent identifier and a readable `%PDF-` child attachment.

Follow [references/existing-item-pdf-reconciliation.md](references/existing-item-pdf-reconciliation.md). Preserve the canonical item's stable key, notes, annotations, tags, collection membership, and citation-key intent. Move or merge only the verified PDF attachment, then remove the temporary duplicate and rerun the duplicate audit. If the identifier differs or the match is ambiguous, stop at `REVIEW_DUPLICATE`.

### 7. Import new items with PDFs

Prefer saving from the publisher/article landing page using Zotero Connector so Zotero receives high-quality metadata and any accessible PDF. If browser interaction is unavailable, use the local Connector fallback:

```powershell
python scripts/zotero_connector_import.py selected-target
python scripts/zotero_connector_import.py import --candidate one-paper.json --target-collection "父分类/目标分类" --pdf paper.pdf --yes
```

Before saving, verify that Zotero Desktop is running and the Connector-selected target matches the requested library/collection. For an already downloaded lawful PDF, use `--pdf path.pdf`. Validate HTTP content type when downloading and require `%PDF-` magic bytes; never attach an HTML login/error page as a PDF. Resolver import can leave a metadata-only item if PDF resolution fails, so use `--resolver --accept-metadata-only-on-resolver-failure` only after disclosing and accepting that risk.

When the publisher requires subscription access, follow [references/institutional-access.md](references/institutional-access.md). At an institution chooser, use only the exact institution supplied by the user in the current task or private local configuration; do not guess among similarly named institutions. Reuse only the user's existing authorized browser session. Never request, read, store, or transmit the user's password or MFA code. If interactive login or second-factor approval is required, pause at that page and ask the user to complete it, then continue from the authenticated landing page.

For an exact existing item, do not use the ordinary new-item path unless the authorized `TEMP_CAPTURE_RECONCILE` workflow applies. A successful Connector response is only a temporary capture until its PDF is reconciled into the canonical item and the temporary parent is removed.

If neither an accessible PDF nor a configured resolver succeeds, report the failure. Import metadata alone only when explicitly authorized.

For an approved OpenAlex OA route, download only explicitly selected work IDs to a staging directory outside Obsidian and Zotero storage:

```powershell
python scripts/openalex_import.py download `
  --candidates "<batch-dir>/openalex_candidates.jsonl" `
  --pdf-dir "<external-staging-dir>" `
  --vault-root "<vault-root>" `
  --openalex-id W1234567890 --max-files 1
```

Direct OA URLs are the default. The paid OpenAlex cached-content route stays off unless the user explicitly accepts the current per-file cost and both `--direct-or-content` and `--accept-openalex-content-cost` are present. Never report the staged file as imported until the Zotero child attachment is reread and verified.

### 8. Verify and audit again

After every write, reread Zotero and verify:

- item key and core metadata;
- membership in the requested collection;
- a child PDF attachment that opens and has nonzero size;
- the recorded access route is correctly labeled `open-access`, `institutional-access`, `repository`, or `user-provided`;
- no new exact or probable duplicate.

For `TEMP_CAPTURE_RECONCILE`, additionally verify that the canonical item now owns the PDF child, the temporary item no longer exists, and the canonical key/notes/annotations/collection memberships were preserved.

Rerun `zotero_dedup.py audit` on the final manifest and audit the target collection. Report each paper as `Saved`, `Reused`, `Needs review`, or `Failed`, with the item key and failure reason. Never claim success from a Connector response alone.

## Bundled scripts

- `scripts/zotero_dedup.py`: read-only local-library status, collection listing, candidate-list deduplication, and library matching.
- `scripts/openalex_import.py`: OpenAlex search, compatible candidate generation, early Zotero duplicate flags, and guarded item-level OA PDF staging.
- `scripts/zotero_connector_import.py`: Connector target probe, candidate/PDF validation, and guarded new-item import.
- `scripts/zotero_webapi_collection.py`: guarded addition of an existing synced item to a Zotero collection through the official Web API.

All mutation commands are dry-run by default and require `--yes`.
