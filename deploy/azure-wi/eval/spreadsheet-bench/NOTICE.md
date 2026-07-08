# NOTICE — Vendored SpreadsheetBench (Attribution & Modifications)

This directory (`eval/spreadsheet-bench/`) vendors a subset of the
**SpreadsheetBench** project and uses its **SpreadsheetBench Verified (400)**
dataset. It is included here as the `spreadsheet-bench` golden-answer evaluation
gate for the `xlsx` skill (cell comparison, complementary to the `gen-eval`
LLM-as-judge gate in `eval/gen-eval/`).

## Attribution (CC BY-SA 4.0)

- **Licensed Material:** SpreadsheetBench (code under `evaluation/` and the
  `spreadsheetbench_verified_400` dataset).
- **Creator / Licensor:** Zeyao Ma, Bohan Zhang, Jing Zhang, Jifan Yu,
  Xiaokang Zhang, Xiaohan Zhang, Sijia Luo, Xi Wang, Jie Tang, et al.
  (SpreadsheetBench, NeurIPS 2024 Datasets & Benchmarks Track).
  SpreadsheetBench Verified was developed in collaboration with Shortcut.AI
  (Fundamental Research Labs).
- **Copyright:** © the SpreadsheetBench authors.
- **License:** Creative Commons Attribution-ShareAlike 4.0 International
  (CC BY-SA 4.0). Full text in `./LICENSE`, canonical URI:
  https://creativecommons.org/licenses/by-sa/4.0/
- **Source (Licensed Material):**
  https://github.com/RUCKBReasoning/SpreadsheetBench
  (vendored from commit `49b73a94775fb489063f60ca1865e3a650079a79`)
- **Homepage / Paper:** https://spreadsheetbench.github.io/ ·
  https://arxiv.org/abs/2406.14991
- **Disclaimer of warranties:** the Licensed Material is provided AS-IS; see
  Section 5 of `./LICENSE`.

## Citation

```bibtex
@article{ma2024spreadsheetbench,
  title={SpreadsheetBench: Towards Challenging Real World Spreadsheet Manipulation},
  author={Ma, Zeyao and Zhang, Bohan and Zhang, Jing and Yu, Jifan and Zhang, Xiaokang and Zhang, Xiaohan and Luo, Sijia and Wang, Xi and Tang, Jie},
  journal={arXiv preprint arXiv:2406.14991},
  year={2024}
}
```

## Modifications made in this repository

Per CC BY-SA 4.0 §3(a)(1)(B), we indicate modifications:

- **`evaluation/` — vendored VERBATIM** from the upstream commit above
  (`evaluation.py`, `open_spreadsheet.py`, `parity_test.py`,
  `scripts/evaluation.sh`). Not modified. Its reusable comparison functions
  (`compare_workbooks`, `cell_level_compare`) are imported by our own drivers.
- **`requirements.txt` — TRIMMED** to the evaluation-only dependencies
  (openpyxl, numpy, tqdm); upstream inference/training deps (transformers,
  vllm, docker, openai) are omitted since we only run the evaluation.
- **`download_data.py` — NEW (this repo).** Downloads/extracts the
  `spreadsheetbench_verified_400` dataset into `eval/spreadsheet-bench/data/`.
- **`selftest.py` — NEW (this repo).** Drives the vendored `compare_workbooks`
  to validate harness correctness (golden-vs-golden pass, golden-vs-perturbed
  fail). It adapts to the Verified-400 layout, which differs from the 912-set
  layout the upstream `evaluation.py` main() hardcodes: Verified-400 uses
  `{i}_{id}_init.xlsx` / `_golden.xlsx` (vs `_input` / `_answer`), a separate
  `answer_sheet` field, and one test case per task.

Any files we author here that adapt the Licensed Material are likewise made
available under **CC BY-SA 4.0** (ShareAlike).
