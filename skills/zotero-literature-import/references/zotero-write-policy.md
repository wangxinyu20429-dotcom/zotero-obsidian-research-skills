# Zotero write and PDF policy

## Supported paths

### Local API

Use `http://127.0.0.1:23119/api` only for reads. Paginate all top-level items; checking only the first page can miss duplicates.

### Connector

Use the Connector HTTP server for new-item capture. Confirm the currently selected library/collection before saving. Prefer article landing pages because Connector translation usually provides better metadata and can discover an accessible PDF.

The bundled importer uses:

- `/connector/getSelectedCollection` for the target;
- `/connector/saveItems` for a new parent item;
- `/connector/saveAttachmentFromResolver` for Zotero/OA PDF resolution;
- `/connector/saveAttachment` for a validated local PDF stream.

Connector sessions are for newly saved items. They are not a general method for filing arbitrary old items into collections.

### Web API

Use the official Zotero Web API to add an existing synced item to a collection. Supply `ZOTERO_USER_ID` and `ZOTERO_API_KEY` through environment variables. Use optimistic concurrency with the item's current version and verify by rereading. Never print the API key.

## Forbidden shortcuts

- Do not write to `zotero.sqlite` or sidecar files.
- Do not create a new item when an exact Zotero item already exists, except for a short-lived Connector capture under the explicitly authorized existing-item PDF reconciliation workflow. The temporary parent must be identity-verified, reconciled, and removed in the same audited task.
- Do not auto-merge or delete existing duplicates.
- Do not bypass paywalls, CAPTCHAs, access controls, or license restrictions.
- Do not attach HTML or an authentication page with a `.pdf` name.
- Do not claim a PDF was saved until the attachment is visible and readable in Zotero.

## PDF source order

1. Publisher-provided accessible PDF discovered from the landing page.
2. Zotero's configured resolver or Unpaywall/Open Access route.
3. Author manuscript in an institutional or subject repository.
4. A user-provided or institutionally authorized downloaded PDF. For institutional access, use only the exact institution supplied in the current task or private local configuration, follow `institutional-access.md`, and label the provenance `institutional-access` rather than `open-access`.

Record the source URL and access status. If only metadata can be saved, require explicit metadata-only permission.

## Existing duplicate handling

When an exact existing item is found, use the same Zotero item key and append the target collection key to its `collections` field through the Web API. If credentials are absent or the item is unsynced, give a manual instruction instead of creating a duplicate.

When the library itself already contains duplicates, report candidate keys and useful evidence: child PDF, attachments, notes, annotations, complete DOI/creators/date, and collection memberships. Let the user choose or use Zotero's duplicate-merging UI.

When the user explicitly authorizes Connector-based PDF recovery for an existing item, read `existing-item-pdf-reconciliation.md`. Temporary duplicate creation is permitted only to obtain an attachment unavailable through resolver-only routes. Preserve the canonical record, verify the temporary PDF before moving/merging it, and remove the temporary parent only after the canonical item visibly owns a readable PDF.

## Official documentation

- Adding items and Connector behavior: https://www.zotero.org/support/adding_items_to_zotero/
- Connector HTTP server: https://www.zotero.org/support/dev/client_coding/connector_http_server
- Web API write requests: https://www.zotero.org/support/dev/web_api/v3/write_requests
- Zotero JavaScript API cautions: https://www.zotero.org/support/dev/client_coding/javascript_api
