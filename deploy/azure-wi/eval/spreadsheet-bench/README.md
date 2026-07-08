# SpreadsheetBench — golden-answer evaluation gate

This directory vendors the **SpreadsheetBench** evaluation harness and uses its
**Verified (400)** dataset as the `spreadsheet-bench` quality gate for the `xlsx`
skill — complementary to the LLM-as-judge `gen-eval` gate in
[`../gen-eval/`](../gen-eval/).

- **`gen-eval`** — excel-gen-eval scores a generated workbook along 8 quality
  dimensions using an LLM judge (no golden answer required).
- **`spreadsheet-bench`** (this dir) — compares a workbook against a **golden
  answer** cell-by-cell over the task's checked range (`answer_position`). A task
  passes only if the output matches the golden (online-judge style).

> Provenance & license: vendored from
> [RUCKBReasoning/SpreadsheetBench](https://github.com/RUCKBReasoning/SpreadsheetBench)
> @ `49b73a9`, **CC BY-SA 4.0**. See [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md).

## Layout

```
eval/spreadsheet-bench/
├── evaluation/            # vendored VERBATIM (evaluation.py, open_spreadsheet.py, ...)
├── download_data.py       # download/extract the Verified-400 dataset
├── selftest.py            # prove the harness is wired correctly (no model needed)
├── requirements.txt       # eval-only deps (openpyxl, numpy, tqdm)
├── LICENSE / NOTICE.md
└── data/                  # downloaded + extracted dataset (git-ignored)
```

The ~15 MB source archive is **downloaded on demand** from the pinned upstream
commit by `download_data.py` and extracted into `data/` (git-ignored) — it is
**not committed**.

## Dataset shape (Verified-400)

- `dataset.json` — 400 task records: `id`, `instruction`, `instruction_type`
  (Cell-Level / Sheet-Level Manipulation), `answer_sheet`, `answer_position`
  (the checked range), `data_position`.
- `spreadsheet/{id}/` — one test case per task: `1_{id}_init.xlsx` (input) and
  `1_{id}_golden.xlsx` (golden answer), plus `prompt.txt`.

Note: this differs from the upstream 912-set layout (`_input`/`_answer` × 3 test
cases). Our drivers reuse the vendored `compare_workbooks()` but adapt to this
layout; see `NOTICE.md`.

## Usage

```bash
pip install -r eval/spreadsheet-bench/requirements.txt

# 1) Download + extract the dataset
python eval/spreadsheet-bench/download_data.py

# 2) Prove the harness is correctly wired (no model / no API key needed)
python eval/spreadsheet-bench/selftest.py --sample 60
```

The self-test validates the comparison harness three ways: a deterministic
synthetic micro-test (identical → equal, one-cell-diff → unequal), and on real
data golden-vs-golden must be **equal** while golden-vs-init must **differ**.

### Scoring a model / skill output

The gate scores a produced output workbook against the golden using the vendored
`compare_workbooks()`. Formula-bearing outputs must first be recalculated so
cached values exist for `openpyxl(data_only=True)`:

```bash
# recalc cached formula values (LibreOffice on Linux/macOS, win32com+Excel on Windows)
python eval/spreadsheet-bench/evaluation/open_spreadsheet.py --dir_path <dir-of-xlsx>
```

Wiring the `xlsx` skill through this gate (generate output per task → recalc →
compare) is driven by `evalkit` (see repo root README).
