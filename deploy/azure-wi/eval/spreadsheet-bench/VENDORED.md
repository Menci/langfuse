# Vendored — how to sync

This directory is vendored verbatim from the `spreadsheet-bench` subtree of
Microsoft-internal `gim-home/excel-skill` (which itself vendors
`RUCKBReasoning/SpreadsheetBench@49b73a9`).

Both upstreams are CC BY-SA 4.0; `NOTICE.md` and `LICENSE` are kept
alongside the code per the license terms. Any modifications made in this
copy must remain CC BY-SA 4.0.

## Refresh

```
rm -rf deploy/azure-wi/eval/spreadsheet-bench
cp -r /path/to/excel-skill/eval/spreadsheet-bench deploy/azure-wi/eval/spreadsheet-bench
# preserve this VENDORED.md
```

Then update this file's SHA reference if the upstream `RUCKBReasoning`
commit changes.
