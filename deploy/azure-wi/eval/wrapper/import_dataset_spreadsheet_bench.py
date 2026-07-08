"""Import SpreadsheetBench Verified-400 into a Langfuse Dataset.

Idempotent: create_dataset upserts by name, create_dataset_item upserts by id.
Re-running this after the dataset already exists silently reconciles any
changed field on each item without duplicating rows.

The xlsx files themselves stay on the PVC (`spreadsheet-bench-data`). Only
their PVC-relative paths land in each DatasetItem, so evaluate jobs open
them from the filesystem instead of pulling MB-sized blobs through the
Langfuse API on every run.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from langfuse import Langfuse


DATASET_NAME = "spreadsheet-bench-v400"
DATASET_DESCRIPTION = (
    "SpreadsheetBench Verified-400 golden-answer benchmark: 400 spreadsheet "
    "manipulation tasks. Each item pairs an initial xlsx + prompt with a "
    "golden xlsx and an `answer_position` cell range for exact-value "
    "comparison.\n\n"
    "Dataset: SpreadsheetBench (Ma et al., NeurIPS 2024). "
    "License: CC BY-SA 4.0. "
    "Source: https://github.com/RUCKBReasoning/SpreadsheetBench."
)


def main() -> int:
    code_root = Path(os.environ.get("SB_CODE_ROOT", "/app/spreadsheet-bench"))
    data_root = code_root / "data" / "verified-400"
    if not (data_root / "dataset.json").exists():
        print(
            f"error: dataset.json not found at {data_root}/dataset.json — "
            "run download_data.py to populate the PVC first",
            file=sys.stderr,
        )
        return 1

    # Reuse the vendored helper so the normalized answer_position we store
    # matches exactly what compare_workbooks parses in the evaluator.
    sys.path.insert(0, str(code_root))
    from download_data import answer_ranges  # type: ignore

    tasks = json.loads((data_root / "dataset.json").read_text())
    lf = Langfuse()

    lf.create_dataset(
        name=DATASET_NAME,
        description=DATASET_DESCRIPTION,
        metadata={
            "license": "CC BY-SA 4.0",
            "source": "https://github.com/RUCKBReasoning/SpreadsheetBench",
            "vendor_commit": "49b73a94775fb489063f60ca1865e3a650079a79",
            "task_count": len(tasks),
        },
    )

    for task in tasks:
        task_id = str(task["id"])
        prompt_file = data_root / "spreadsheet" / task_id / "prompt.txt"
        prompt = (
            prompt_file.read_text(encoding="utf-8").strip()
            if prompt_file.exists()
            else str(task.get("instruction", ""))
        )
        rel_init = f"spreadsheet/{task_id}/1_{task_id}_init.xlsx"
        rel_golden = f"spreadsheet/{task_id}/1_{task_id}_golden.xlsx"

        lf.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=f"sb-v400-{task_id}",
            input={
                "task_id": task_id,
                "prompt": prompt,
                "init_xlsx_pvc_path": rel_init,
            },
            expected_output={
                "answer_position": answer_ranges(task),
                "instruction_type": task["instruction_type"],
                "answer_sheet": task.get("answer_sheet"),
                "golden_xlsx_pvc_path": rel_golden,
            },
            metadata={
                "task_id": task_id,
                "license": "CC BY-SA 4.0",
            },
        )

    lf.flush()
    print(f"imported {len(tasks)} items into dataset '{DATASET_NAME}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
