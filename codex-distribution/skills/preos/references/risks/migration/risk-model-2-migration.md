# PREOS Risk Corpus v2 Migration Plan

## Objective

Introduce the attached 4,337-entry five-dimension catalogue as PREOS Risk Corpus v2 without deleting or silently reinterpreting the existing 1,130-entry corpus.

## Required migration sequence

1. Freeze the current PREOS 1,130-record corpus as `v1` and record its existing hashes.
2. Add this package's `risk-corpus-v2` as a parallel corpus.
3. Validate exactly 4,337 records, exactly 40 fields per record, and dimension totals of 1,406 universal, 1,450 industry, 753 product, 328 jurisdiction, and 400 architecture.
4. Build a v1-to-v2 crosswalk using canonical name, aliases, semantic review, source provenance, and human review for ambiguous matches.
5. Classify each v1 record as PRESERVED_EXACT, PRESERVED_RENAMED, PRESERVED_CONTEXTUAL, SPLIT, MERGED_WITH_PROVENANCE, or UNRESOLVED. No v1 record may disappear without an explicit migration disposition.
6. Update PREOS selectors to query v2 by risk ID, dimension, category, owner, component, project profile and keyword without loading the entire catalogue.
7. Run existing PREOS tests against v1 and new tests against v2 during a compatibility window.
8. Change the default corpus pointer only after crosswalk completeness is 100 percent and all migration gates pass.
9. Retain v1 for historical evidence replay and old Project Contracts.

## Stop conditions

- Any v1 risk has no migration disposition.
- v2 count is not 4,337.
- Any v2 record has fewer or more than 40 fields.
- Duplicate risk IDs are unresolved.
- Project contracts cannot declare which corpus version they use.
- Evidence generated under v1 would be silently reinterpreted under v2.
