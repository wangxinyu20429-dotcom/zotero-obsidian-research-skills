# Input manifest contract

Formal runs require one JSON file:

```json
{
  "manifest_version": "0.2",
  "source_batch_id": "batch-id",
  "analysis_mode": "formal",
  "research_question": "question",
  "literature": [
    {
      "canonical_literature_id": "LIT-...",
      "source_path": "relative/path",
      "selection_status": "included"
    }
  ],
  "expected_counts": {}
}
```

`expected_counts` and each child field are optional. Supported keys include `sample_literature`, `lightweight_profiles`, `core_deep_reads` and `candidate_directions_max`. Their values belong to the current test/run manifest only; missing means “no quantity gate”.

Rules:

1. `manifest_version`, `source_batch_id`, `analysis_mode`, `research_question` and `literature` are required in formal mode.
2. Every included item needs one stable ID and one local source path.
3. Only `selection_status: included` enters formal downstream analysis.
4. A manifest must be immutable during a formal run. Amendments create a new manifest/version and audit record.
5. Multiple competing manifests, unknown IDs or batch mismatch block formal mode.
