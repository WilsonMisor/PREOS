# Baseline 75 Controls

The single machine-readable canonical baseline is the source-package member `baseline_75_controls.json`. The exact original package is stored as checksum-verified base64 chunks under `source-package/package-chunks/` and reconstructed byte-for-byte by PREOS. `references/baseline/baseline-75-controls.json` is a stable repository pointer, not a duplicate control definition.

The original human-readable rendering is the source-package member `baseline_75_controls.md`.

Use:

```bash
python scripts/extract-source.py baseline_75_controls.json
python scripts/extract-source.py baseline_75_controls.md
```

Do not maintain a second editable copy of the 75 definitions. Project repositories store applicability and assessment state, not another baseline catalogue.
