# SpreadsheetBench evaluation gate image.
#
# Runtime is deliberately narrow: openpyxl reads / writes the .xlsx cells,
# LibreOffice runs headless to re-cache formula values (openpyxl reads the
# cached value only, so any formula-emitting skill output must be recalced
# once before comparison), and the Langfuse SDK writes traces + scores.
#
# Does NOT include Copilot CLI, LLM providers, or the gen-eval judge — this
# image is the objective (golden-answer) gate only. Predicted xlsx files are
# supplied to the container as a mounted directory; xlsx generation happens
# outside the cluster.
#
# Vendored code and the Verified-400 dataset are CC BY-SA 4.0. See
# eval/spreadsheet-bench/{NOTICE,LICENSE}.md.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# libreoffice-calc: formula recalculation (headless CLI reachable as `soffice`).
# ca-certificates: TLS for the dataset download from raw.githubusercontent.com.
# curl: convenience for probes / manual smoke tests.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-calc \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY deploy/azure-wi/eval/spreadsheet-bench/requirements.txt /tmp/sb-requirements.txt
RUN pip install --no-cache-dir -r /tmp/sb-requirements.txt langfuse>=2.60.0

COPY deploy/azure-wi/eval/spreadsheet-bench/ /app/spreadsheet-bench/
COPY deploy/azure-wi/eval/wrapper/ /app/wrapper/

ENV SB_DATA_ROOT=/data/verified-400 \
    SB_CODE_ROOT=/app/spreadsheet-bench \
    PYTHONPATH=/app

# No default CMD: this image is a toolbox. Kubernetes Jobs pick the entry
# script (selftest / import_dataset / evaluate) via `command:` in the pod
# spec.
