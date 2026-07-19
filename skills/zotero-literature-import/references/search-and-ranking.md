# Search, ranking, and candidate schema

## Search policy

Use a query matrix rather than a single phrase:

- core concept and close synonyms;
- mechanism/method terms;
- application or population terms;
- exclusions and date bounds;
- known field-specific controlled vocabulary.

Search at least two independent sources when practical. Favor Crossref, PubMed or another domain index, OpenAlex/Semantic Scholar, publisher pages, and institutional repositories. Use Google Scholar, Web of Science, or Scopus only when access is available and label access limitations.

Rank by:

1. direct relevance to the research question;
2. study design and evidence strength;
3. metadata/identity confidence;
4. current, verifiable venue evidence;
5. citation influence or recency, interpreted in field context;
6. lawful PDF availability.

High impact does not compensate for poor relevance. Include seminal older papers when justified.

## Venue evidence

For each selected item, record one of:

- `verified_metric`: metric name/value, provider, metric year, lookup date, URL;
- `verified_indexing`: SCI/SCIE or database coverage, provider, lookup date, URL;
- `proxy`: citations, society flagship status, domain reputation, or other explicitly named proxy;
- `unverified`: no reliable current evidence.

Never label a journal as SCI top-tier or state an impact factor without a current source. JCR values are year-specific and may require licensed access.

## Candidate JSON

Accept either a JSON array or `{ "candidates": [...] }`. Recommended record:

```json
{
  "title": "Required article title",
  "authors": [
    {"firstName": "Ada", "lastName": "Lovelace", "creatorType": "author"}
  ],
  "year": "2025",
  "date": "2025-06-01",
  "journal": "Journal name",
  "volume": "12",
  "issue": "3",
  "pages": "100-115",
  "doi": "10.xxxx/example",
  "pmid": "",
  "pmcid": "",
  "arxiv_id": "",
  "url": "https://publisher.example/article",
  "abstract": "",
  "tags": ["topic"],
  "pdf_url": "https://repository.example/article.pdf",
  "pdf_access": {"status": "open", "source": "repository", "checked_at": "2026-07-19"},
  "metadata_sources": ["https://doi.org/10.xxxx/example"],
  "venue_evidence": {"status": "verified_metric", "source": "...", "year": "2025", "checked_at": "2026-07-19"},
  "selection_reason": "Directly tests the requested mechanism"
}
```

Do not place API keys, cookies, or authentication headers in candidate files.

## Duplicate rules

Normalize DOI by lowercasing and removing `https://doi.org/`, `http://dx.doi.org/`, and `doi:`. Normalize titles with Unicode NFKC, lowercase, punctuation removal, and whitespace folding.

Use exact persistent identifiers first. For fallback matching, require high title similarity plus compatible author/year; label rather than auto-resolve uncertainty. Same DOI with materially different title/author/year is a metadata conflict and must be verified before mutation.
