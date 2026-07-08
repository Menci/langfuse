# Langfuse-integrated wrappers around the vendored gates.

Files land here as the eval platform onboards each gate:

- `import_dataset_spreadsheet_bench.py` — one-shot: Verified-400 → Langfuse Dataset
- `evaluate_spreadsheet_bench.py` — per-run: predicted xlsx dir → Trace/Score + DatasetRunItem

Nothing here today; the image intentionally builds with an empty wrapper
directory so the layer is a placeholder that later Kaniko builds fill in
without a Dockerfile change.
