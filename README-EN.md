# ExportTweetsToPDF-Sdanderd (Standard Edition)

English | [中文版](./README.md)

## Features

- CSV input -> PDF output (`Date | Content`)
- Media download cache -> offline PDF rendering
- Date range filtering + sorting
- Basic concurrency (default: `4`)
- Basic font coverage (Chinese + English)
- Auto clean media cache after PDF generation

## Python Version Support

- Minimum supported version: `Python 3.11`
- Recommended version: `Python 3.12`
- Note: `Python 3.13/3.14` may hit dependency wheel/system-library differences in some environments and are not the default recommendation for the standard edition.

## Installation

```bash
cd [Your Path]/ExportTweetsToPDF/ExportTweetsToPDF-Sdanderd
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

### 1) Initialize resources (download fonts)

```bash
python tweetpdf.py --init
```

### 2) Show version

```bash
python tweetpdf.py --version
```

### 3) Basic export (default concurrency = 4)

```bash
python tweetpdf.py --csv /path/to/TwExport_xxx_Posts.csv
```

### 4) Date range + sorting

> Date filtering must be provided as a pair: `--start` and `--end`.

```bash
python tweetpdf.py \
  --csv /path/to/TwExport_xxx_Posts.csv \
  --start 2026-01-01 \
  --end 2026-02-11 \
  --sort desc
```

## Arguments

- `--csv` input CSV path (required for export)
- `--out` output PDF path (default: same CSV name with `.pdf`)
- `--start` start date (YYYY-MM-DD)
- `--end` end date (YYYY-MM-DD)
- `--sort asc|desc` sort by date (default: `asc`)
- `--concurrency` media download concurrency (default: `4`)
- `--allow-hosts` media host allowlist
- `--download-dir` temporary cache directory (default: `.tweetpdf_cache`)
- `--init` initialize font resources and exit
- `--version` print version and exit
- `--help` show help

## Runtime Output

During execution, it prints stage information:

- Font check/download
- CSV loading and filtering
- Media downloading
- PDF rendering
- Cache cleanup

After completion, it prints:

- Output PDF path
- Removed cache file count and freed disk size

## Open Source License and Copyright

- This project is licensed under [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
- Copyright (C) 2020 - Present, TanBQ.
- Use, modification, and distribution must comply with Apache-2.0 terms.

