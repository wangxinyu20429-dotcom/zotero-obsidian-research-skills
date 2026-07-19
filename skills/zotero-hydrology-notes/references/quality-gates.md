# Quality gates

Run every gate before saving a note.

## Identity

- The title, authors, year, DOI, Zotero item key, and attachment key all belong to the same paper.
- Ambiguous matches were resolved explicitly.
- `source_file` exists and `source_url` uses the top-level item key.

## Coverage

- The live template was read in full and all sections remain present.
- Abstract/introduction, data, methods, results, discussion/conclusion, and relevant captions were read or explicitly marked unavailable.
- Unused method modules say `不适用`; missing evidence says `未报告` or `[待核验]`.

## Evidence

- Major claims have section/page/figure/table anchors where available.
- Quantitative claims retain value, unit, condition, and comparison baseline.
- Direct facts, author interpretations, AI summaries, and research judgments are labeled correctly.
- No page number, equation, statistic, mechanism, constraint, limitation, or reference was invented.
- Caption-only analysis does not claim visual inspection.

## Consistency

- Terminology, abbreviations, symbols, units, time steps, and spatial scales are consistent.
- The five-sentence summary matches the evidence chain and stated boundaries.
- The final evaluation does not exceed the strength of the available evidence.
- In batch mode, evidence and numbers are not attributed to the wrong paper.

## Filesystem

- The destination is the configured `文献笔记` directory.
- No existing note with the same `zotero_item_key` is overwritten.
- Temporary extraction files are not written into the final note directory.
