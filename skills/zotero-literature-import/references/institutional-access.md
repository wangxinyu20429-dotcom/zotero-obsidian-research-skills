# Institutional PDF access

Use this route only for lawful access under the user's own institutional entitlement. It is an authenticated retrieval route, not an access-control bypass.

## Institution selection

- Obtain the exact institution name from the current user request or a private user-controlled local setting.
- Do not embed a user's institution in this portable Skill, logs intended for publication, examples, or public repositories.
- Do not guess among similarly named institutions. Ask the user to choose when the exact entry is ambiguous.
- Prefer a publisher's official `Access through your institution`, `Institutional sign in`, Shibboleth, OpenAthens, or WAYF flow. A university WebVPN already opened and authenticated by the user is also acceptable.

## Authentication boundary

1. Work in the user's normal browser through `web-access`, preserving existing tabs and login state.
2. Create a separate task-owned tab when possible. Do not close or repurpose the user's existing WebVPN, library, or publisher tabs.
3. On an institution chooser, select only the user-confirmed exact entry and verify the redirect belongs to the publisher, that institution, or its authorized identity/VPN service.
4. If a username, password, CAPTCHA, MFA code, QR confirmation, or consent decision is required, stop and ask the user to complete it in the browser. Do not inspect DOM values, cookies, password managers, clipboard contents, or network tokens containing credentials.
5. After the user completes authentication, continue from the publisher article landing page and use Zotero Connector so translator metadata and the licensed PDF are captured together.

## Retrieval and rate limits

- Retrieve only the specific papers in the approved manifest, one article at a time.
- Do not bulk crawl a publisher, enumerate licensed holdings, evade download limits, or retry aggressively after an access denial.
- Treat a successful institutional session as permission to fetch the approved article, not as permission to expand the search or download set.
- If the publisher displays a license restriction, robot warning, CAPTCHA, or temporary block, stop that route and report it.

## Verification and provenance

- Label the source as `institutional-access`, not `open-access`.
- Record the article landing URL, publisher, institution name, access date, and whether Connector or a user-authorized browser download supplied the PDF. Do not record session tokens or credential-bearing URLs.
- Require `application/pdf`, nonzero size, `%PDF-` magic bytes, and identity compatibility with the target DOI/title before attaching or reconciling.
- Never attach a login, WAYF, consent, proxy error, or HTML access-denied page with a `.pdf` extension.
- If authentication succeeds but no readable PDF is available, report `BLOCKED_NO_PDF` or use a lawful repository route; do not bypass the publisher.

## Existing Zotero item

If an exact existing Zotero item lacks a PDF, institutional access changes only the retrieval route. The authorization and cleanup requirements in `existing-item-pdf-reconciliation.md` still apply: Connector capture is temporary, the PDF must be verified, the canonical record must be preserved, and the temporary duplicate must be removed only after reconciliation succeeds.
