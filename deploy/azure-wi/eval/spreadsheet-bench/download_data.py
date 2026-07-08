"""Download / extract the SpreadsheetBench **Verified (400)** dataset.

The 15 MB source archive is **not committed** to this repo; it is downloaded
on demand from the pinned upstream commit and extracted (idempotently) into
``eval/spreadsheet-bench/data/verified-400/`` (git-ignored working copy).

Usage:
    python eval/spreadsheet-bench/download_data.py            # ensure extracted
    python eval/spreadsheet-bench/download_data.py --force    # re-extract

Dataset & framework: https://github.com/RUCKBReasoning/SpreadsheetBench
License: CC BY-SA 4.0 (see ./LICENSE and ./NOTICE.md).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# Pinned upstream commit for reproducible downloads (used only if the
# LFS-committed archive is absent).
_PINNED_SHA = "49b73a94775fb489063f60ca1865e3a650079a79"
ARCHIVE_NAME = "spreadsheetbench_verified_400.tar.gz"
ARCHIVE_TOPLEVEL = "spreadsheetbench_verified_400"
DOWNLOAD_URL = (
    f"https://raw.githubusercontent.com/RUCKBReasoning/SpreadsheetBench/"
    f"{_PINNED_SHA}/data/{ARCHIVE_NAME}"
)

# Dataset lives next to this framework: eval/spreadsheet-bench/data/ (git-ignored).
DATASET_DIR = Path(__file__).resolve().parent / "data"
ARCHIVE_PATH = DATASET_DIR / ARCHIVE_NAME
EXTRACT_DIR = DATASET_DIR / "verified-400"  # contains dataset.json + spreadsheet/


def _download_archive(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {ARCHIVE_NAME} from {DOWNLOAD_URL} ...")
    urllib.request.urlretrieve(DOWNLOAD_URL, str(dest))
    print(f"  saved {dest} ({dest.stat().st_size} bytes)")


def _extract_archive(archive: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    with tempfile.TemporaryDirectory(dir=str(dest.parent)) as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:gz") as tf:
            # filter="data" guards against path traversal (Python >= 3.12).
            try:
                tf.extractall(tmp_path, filter="data")
            except TypeError:  # older Python without the filter kwarg
                tf.extractall(tmp_path)
        top = tmp_path / ARCHIVE_TOPLEVEL
        root = top if top.is_dir() else tmp_path
        shutil.move(str(root), str(dest))


def ensure_dataset(force: bool = False) -> Path:
    """Ensure the Verified-400 dataset is extracted; return its root dir.

    Precedence: existing extraction -> LFS-committed archive -> download.
    """
    dataset_json = EXTRACT_DIR / "dataset.json"
    if not force and dataset_json.exists():
        return EXTRACT_DIR

    if not ARCHIVE_PATH.exists():
        _download_archive(ARCHIVE_PATH)
    elif ARCHIVE_PATH.stat().st_size < 1024:
        # Likely an un-smudged Git LFS pointer file; fetch the real blob.
        raise RuntimeError(
            f"{ARCHIVE_PATH} looks like an unresolved Git LFS pointer "
            f"({ARCHIVE_PATH.stat().st_size} bytes). Run 'git lfs pull' first, "
            f"or delete it to re-download."
        )

    print(f"Extracting {ARCHIVE_PATH.name} -> {EXTRACT_DIR} ...")
    _extract_archive(ARCHIVE_PATH, EXTRACT_DIR)
    if not dataset_json.exists():
        raise RuntimeError(f"Extraction failed: {dataset_json} not found")
    return EXTRACT_DIR


# ── Dataset accessors (shared by selftest.py and the evalkit objective gate) ──

def load_records(root: Path | None = None) -> list[dict]:
    """Load dataset.json (list of task records)."""
    root = root or EXTRACT_DIR
    with open(root / "dataset.json", encoding="utf-8") as fp:
        return json.load(fp)


def task_dir(record: dict, root: Path | None = None) -> Path:
    root = root or EXTRACT_DIR
    return root / "spreadsheet" / str(record["id"])


def answer_ranges(record: dict) -> str:
    """Return an ``answer_position`` string compatible with the vendored
    ``compare_workbooks``: ``sheet!range`` (comma-separated for multiples).

    Verified-400 stores the sheet separately in ``answer_sheet`` and a bare
    range in ``answer_position`` (e.g. ``LISTS`` + ``A3:D32``). If the sheet is
    already embedded (contains ``!``) it is returned unchanged.
    """
    pos = str(record.get("answer_position", "")).strip()
    sheet = str(record.get("answer_sheet", "")).strip()
    if not pos:
        return pos
    if "!" in pos or not sheet:
        return pos
    parts = [p.strip() for p in pos.split(",") if p.strip()]
    return ",".join(f"{sheet}!{p}" for p in parts)


def iter_test_cases(record: dict, root: Path | None = None):
    """Yield ``(idx, init_path, golden_path)`` for each test case of a task.

    Verified-400 mostly uses ``{idx}_{id}_init.xlsx`` / ``{idx}_{id}_golden.xlsx``
    (typically a single test case, idx=1). A handful of records use the simpler
    ``initial.xlsx`` / ``golden.xlsx`` naming, and at least one has a golden file
    whose embedded id is a typo (e.g. ``1_43930_golden.xlsx`` for task 42930) —
    both variants are handled so no scoreable task is silently dropped.
    """
    root = root or EXTRACT_DIR
    tid = str(record["id"])
    tdir = root / "spreadsheet" / tid
    if not tdir.is_dir():
        return

    def _golden_for(idx: str) -> Path | None:
        exact = tdir / f"{idx}_{tid}_golden.xlsx"
        if exact.exists():
            return exact
        # Tolerate a mistyped id in the golden filename (same idx prefix).
        hits = sorted(glob.glob(os.path.join(str(tdir), f"{idx}_*_golden.xlsx")))
        if hits:
            return Path(hits[0])
        simple = tdir / "golden.xlsx"
        return simple if simple.exists() else None

    inits = sorted(glob.glob(os.path.join(str(tdir), f"*_{tid}_init.xlsx")))
    if inits:
        for init in inits:
            idx = Path(init).name.split("_", 1)[0]
            golden = _golden_for(idx)
            if golden:
                yield idx, Path(init), golden
        return

    # Fallback: simple ``initial.xlsx`` / ``golden.xlsx`` naming.
    init = tdir / "initial.xlsx"
    golden = tdir / "golden.xlsx"
    if init.exists() and golden.exists():
        yield "1", init, golden


def dataset_summary(root: Path | None = None) -> dict:
    root = root or EXTRACT_DIR
    records = load_records(root)
    complete = sum(1 for r in records if list(iter_test_cases(r, root)))
    return {
        "records": len(records),
        "tasks_with_testcases": complete,
        "tasks_incomplete": len(records) - complete,
        "root": str(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-extract even if present")
    args = parser.parse_args()

    ensure_dataset(force=args.force)
    summary = dataset_summary()
    print("\nSpreadsheetBench Verified-400 ready:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
