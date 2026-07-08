"""Run the SpreadsheetBench golden-answer evaluator against a set of
predicted xlsx files and log every case to Langfuse.

Uses `DatasetClient.run_experiment()` (Langfuse SDK v4) so the SDK owns
per-item trace + DatasetRunItem + score wiring; we only supply a `task`
that locates the predicted xlsx and an `evaluator` that wraps
compare_workbooks().

Predicted xlsx location is a template so the same job can score both:

  # A real agent's flat outputs directory:
  --predicted-dir /predicted --predicted-template "{task_id}.xlsx"

  # The no-op `init` baseline sitting inside the vendored dataset tree:
  --predicted-dir /app/spreadsheet-bench/data/verified-400/spreadsheet \
  --predicted-template "{task_id}/1_{task_id}_init.xlsx"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from langfuse import Langfuse
from langfuse.experiment import Evaluation


def _make_task(predicted_root: Path, template: str):
    def task(*, item, **_kwargs):
        task_id = item.input["task_id"]
        relative = template.format(task_id=task_id)
        candidate = predicted_root / relative
        exists = candidate.is_file()
        return {
            "task_id": task_id,
            "predicted_exists": exists,
            "predicted_path": str(candidate) if exists else None,
            "predicted_template": template,
        }

    return task


def _make_evaluator(data_root: Path, compare_workbooks):
    def evaluator(*, input, output, expected_output, **_kwargs):
        itype = (expected_output or {}).get("instruction_type") or "unknown"
        # Always emit the categorical dim so we can filter pass rate by
        # Cell-Level vs Sheet-Level in the Langfuse UI, even for skipped items.
        type_score = Evaluation(
            name="instruction_type",
            value=itype,
            data_type="CATEGORICAL",
        )
        if not output.get("predicted_exists"):
            return [
                Evaluation(
                    name="pass",
                    value=0,
                    data_type="BOOLEAN",
                    comment="no predicted xlsx at expected path",
                ),
                type_score,
            ]
        golden = data_root / expected_output["golden_xlsx_pvc_path"]
        try:
            ok, detail = compare_workbooks(
                str(golden),
                output["predicted_path"],
                expected_output["instruction_type"],
                expected_output["answer_position"],
            )
        except Exception as exc:
            return [
                Evaluation(
                    name="pass",
                    value=0,
                    data_type="BOOLEAN",
                    comment=f"compare_workbooks raised: {exc}"[:500],
                ),
                type_score,
            ]
        return [
            Evaluation(
                name="pass",
                value=1 if ok else 0,
                data_type="BOOLEAN",
                comment=(detail or ("match" if ok else ""))[:500],
            ),
            type_score,
        ]

    return evaluator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="spreadsheet-bench-v400")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--predicted-dir", required=True)
    parser.add_argument(
        "--predicted-template",
        default="{task_id}.xlsx",
        help="Path relative to --predicted-dir, with {task_id} placeholder",
    )
    parser.add_argument("--description", default=None)
    parser.add_argument("--max-concurrency", type=int, default=8)
    args = parser.parse_args()

    code_root = Path(os.environ.get("SB_CODE_ROOT", "/app/spreadsheet-bench"))
    data_root = code_root / "data" / "verified-400"

    sys.path.insert(0, str(code_root))
    from evaluation.evaluation import compare_workbooks  # type: ignore

    predicted_root = Path(args.predicted_dir)
    lf = Langfuse()
    ds = lf.get_dataset(args.dataset)

    result = ds.run_experiment(
        name=args.run_name,
        description=args.description,
        task=_make_task(predicted_root, args.predicted_template),
        evaluators=[_make_evaluator(data_root, compare_workbooks)],
        max_concurrency=args.max_concurrency,
    )

    total = len(result.item_results)
    passes = sum(
        1
        for r in result.item_results
        for e in (r.evaluations or [])
        if e.name == "pass" and float(e.value or 0) >= 0.5
    )
    print(
        f"dataset={args.dataset} run={args.run_name} "
        f"predicted_root={predicted_root} template={args.predicted_template}"
    )
    print(f"total={total} pass={passes} pass_rate={passes / total:.3f}" if total else "no items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
