# Existing-item PDF reconciliation

Use this workflow when a canonical Zotero item already exists without a PDF, while Zotero Connector can capture the article and its PDF from the browser. Connector sessions are designed around newly saved parents, so reconciliation must be explicit, auditable, and temporary.

## Authorization gate

Require explicit authorization in the current task for all three actions:

1. create a temporary duplicate with Connector;
2. move/merge its verified PDF into the canonical item;
3. remove the temporary duplicate after verification.

Without that authorization, stop and give the user manual Connector/merge instructions. Do not infer destructive permission from a general request to download PDFs.

## Per-item procedure

1. Record the canonical item key, persistent identifier, title, collection keys, notes/annotations count, tags, and current child attachments.
2. Open the publisher/article landing page in the user's authorized browser session. Prefer the landing page over a bare PDF URL so Zotero Connector can use the site translator and authenticated attachment route. If subscription access is required, follow `institutional-access.md` and use only the institution supplied in the current task or private local configuration.
3. Save with Zotero Connector to the confirmed target collection. Treat the resulting parent as temporary.
4. Reread Zotero and identify the new parent by exact DOI/PMID/PMCID/arXiv ID. Require exactly one canonical item and one new temporary item. More matches or conflicting metadata mean `REVIEW_DUPLICATE`.
5. Verify the temporary child attachment:
   - content type is `application/pdf`;
   - local file exists and has nonzero size;
   - first bytes are `%PDF-`;
   - title/DOI in extracted text is compatible with the target paper.
6. Reconcile using Zotero's Duplicate Items merge UI when practical. Select the canonical metadata version and confirm that attachments from the temporary item are retained. If using the Zotero JavaScript API, reparent only the verified PDF attachment to the canonical item inside a transaction, reread it, then erase the temporary parent only after the canonical child is visible.
7. Verify preservation of the canonical item's key intent, collection membership, notes, annotations, and tags. Record any key change caused by Zotero's merge behavior.
8. Rerun the duplicate audit. Report `Saved` only when the canonical item owns a readable PDF and no temporary exact duplicate remains.

## Batch safeguards

- Process one publisher page at a time and pace requests conservatively.
- Keep a manifest mapping `canonical_key`, `temporary_key`, DOI, temporary PDF key, final PDF key, verification result, and cleanup result.
- Never merge by title alone when a persistent identifier is available.
- Never erase a temporary item while its PDF is the only verified copy.
- Stop for the user on CAPTCHA, institutional reauthentication, MFA, or credential entry. Stop the workflow on identifier conflict, missing PDF, ambiguous duplicates, or publisher download restrictions.

## Required statuses

- `TEMP_CAPTURE_CREATED`: Connector created the temporary parent.
- `TEMP_PDF_VERIFIED`: temporary PDF passed identity and file validation.
- `RECONCILED`: verified PDF is now a child of the canonical item.
- `TEMP_CLEANED`: temporary parent was removed after reconciliation.
- `REVIEW_DUPLICATE`: identifier or parent selection is ambiguous.
- `FAILED`: include the exact stage and reason.
