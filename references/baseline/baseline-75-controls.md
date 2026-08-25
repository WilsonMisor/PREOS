# Baseline 75 Controls

The single machine-readable canonical baseline is `source-package/original-package.zip::baseline_75_controls.json` and contains exactly controls 1 through 75. `references/baseline/baseline-75-controls.json` is a stable repository pointer to that source, not a duplicate control definition.

The original human-readable rendering is preserved byte-for-byte in the same ZIP as `baseline_75_controls.md`.

Use:

```bash
python scripts/extract-source.py baseline_75_controls.json
python scripts/extract-source.py baseline_75_controls.md
```

Do not maintain a second editable copy of the 75 definitions. Project repositories store applicability and assessment state, not another baseline catalogue.
