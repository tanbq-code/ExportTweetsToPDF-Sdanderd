#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2020–2026 TanBQ

"""
ExportTweetsToPDF-Standard
Minimal standard edition for TwExport CSV -> PDF export.

Author: TanBQ.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from tqdm import tqdm

VERSION = "1.0.0-Standard"
COPYRIGHT = "@Copyright (C) 2020 - {year} by TanBQ."
DEFAULT_ALLOW_HOSTS = ("pbs.twimg.com", "video.twimg.com")
DEFAULT_CONCURRENCY = 4

CAND_CREATED_AT = ("Created At", "created_at", "Date", "date", "Time", "time")
CAND_TEXT = ("Text", "text", "Full Text", "full_text", "Content", "content")
CAND_URL = ("Tweet URL", "tweet_url", "URL", "url", "Link", "link")
CAND_MEDIA_URLS = ("media_urls", "Media URLs", "media", "images", "image_urls")


@dataclass(frozen=True)
class FontSpec:
    family: str
    filename: str
    format_hint: str
    url: str


FONT_SPECS: Tuple[FontSpec, ...] = (
    FontSpec(
        family="Noto Sans",
        filename="NotoSans-Regular.ttf",
        format_hint="truetype",
        url="https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
    ),
    FontSpec(
        family="Noto Sans CJK SC",
        filename="NotoSansCJKsc-Regular.otf",
        format_hint="opentype",
        url="https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    ),
)


@dataclass
class TweetRow:
    tweet_id: str
    created_at: datetime
    text: str
    text_html: str
    url: str
    media_urls: List[str]
    media_files: List[str]


def _print_banner() -> None:
    print(COPYRIGHT.format(year=datetime.now().year))


def _pick_col(header: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    exact = {h.strip(): h for h in header}
    for name in candidates:
        if name in exact:
            return exact[name]
    lower = {h.strip().lower(): h for h in header}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _parse_datetime(raw: str) -> datetime:
    s = (raw or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception as exc:
        raise ValueError(f"Unsupported datetime format: {s!r}") from exc


def _parse_media_urls(cell: str) -> List[str]:
    if not cell:
        return []
    parts = re.split(r"[\r\n]+|[;,]\s*", str(cell).strip())
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if p.startswith("http://") or p.startswith("https://"):
            out.append(p)
    return out


def _safe_tweet_id(value: str, fallback: str = "tweet") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "").strip())[:80].strip("._")
    return cleaned or fallback


def _safe_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    m = re.search(r"\.([A-Za-z0-9]{2,5})$", path)
    return "." + m.group(1).lower() if m else ".bin"


def _allowed_host(url: str, allow_hosts: Sequence[str]) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return any(host == h.lower() or host.endswith("." + h.lower()) for h in allow_hosts)


def _text_to_html(text: str) -> str:
    # Safe rendering: unescape already happened in CSV parsing.
    return html.escape(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _read_rows(csv_path: Path) -> List[TweetRow]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        col_dt = _pick_col(header, CAND_CREATED_AT)
        col_text = _pick_col(header, CAND_TEXT)
        col_url = _pick_col(header, CAND_URL)
        col_media = _pick_col(header, CAND_MEDIA_URLS)

        if not col_dt or not col_text or not col_url:
            raise SystemExit(
                "Could not find required columns.\n"
                f"Header={header}\n"
                "Need one of: created_at/date/time, text/full_text, tweet_url/url."
            )

        rows: List[TweetRow] = []
        for row in reader:
            dt_raw = (row.get(col_dt, "") or "").strip()
            if not dt_raw:
                continue
            try:
                created_at = _parse_datetime(dt_raw)
            except Exception:
                continue

            text = html.unescape(row.get(col_text, "") or "")
            url = (row.get(col_url, "") or "").strip()
            tweet_id = str(row.get("ID") or row.get("id") or "").strip() or url.rstrip("/").split("/")[-1]
            tweet_id = _safe_tweet_id(tweet_id)
            media_urls = _parse_media_urls(row.get(col_media, "") if col_media else "")
            rows.append(
                TweetRow(
                    tweet_id=tweet_id,
                    created_at=created_at,
                    text=text,
                    text_html="",
                    url=url,
                    media_urls=media_urls,
                    media_files=[],
                )
            )
    return rows


def _parse_date_range(start: Optional[str], end: Optional[str]) -> Tuple[Optional[date], Optional[date]]:
    if bool(start) != bool(end):
        raise SystemExit("Date filter requires both --start and --end (YYYY-MM-DD).")
    if not start and not end:
        return None, None
    try:
        s = date.fromisoformat(start or "")
        e = date.fromisoformat(end or "")
    except ValueError as exc:
        raise SystemExit("Invalid date format. Use YYYY-MM-DD.") from exc
    if s > e:
        raise SystemExit("--start cannot be later than --end.")
    return s, e


def _filter_rows(rows: Sequence[TweetRow], start: Optional[date], end: Optional[date]) -> List[TweetRow]:
    if not start and not end:
        return list(rows)
    out: List[TweetRow] = []
    for t in rows:
        d = t.created_at.date()
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(t)
    return out


def _download_media(
    rows: Sequence[TweetRow],
    media_cache_dir: Path,
    allow_hosts: Sequence[str],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_s: float = 20.0,
    max_bytes: int = 10 * 1024 * 1024,
) -> None:
    media_cache_dir.mkdir(parents=True, exist_ok=True)

    tasks: List[Tuple[TweetRow, str, Path]] = []
    for t in rows:
        for i, url in enumerate(t.media_urls):
            if not _allowed_host(url, allow_hosts):
                continue
            out = media_cache_dir / f"{t.tweet_id}_{i:02d}{_safe_ext_from_url(url)}"
            tasks.append((t, url, out))

    if not tasks:
        print("[4/6] Media download skipped (no downloadable media).")
        return

    print(f"[4/6] Downloading media ({len(tasks)} files, concurrency={concurrency})...")
    pbar = tqdm(total=len(tasks), desc="Downloading media", unit="file")
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(timeout_s)

    async def runner() -> None:
        import asyncio

        async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
            sem = asyncio.Semaphore(concurrency)

            async def fetch_one(t: TweetRow, url: str, out: Path) -> None:
                try:
                    if out.exists() and out.stat().st_size > 0:
                        t.media_files.append(out.resolve().as_uri())
                        return

                    backoff = 1.0
                    for attempt in range(4):
                        try:
                            async with sem:
                                r = await client.get(url, headers={"User-Agent": "tweetpdf-standard/1.0"})
                            if r.status_code == 200 and r.content:
                                if len(r.content) > max_bytes:
                                    return
                                out.write_bytes(r.content)
                                t.media_files.append(out.resolve().as_uri())
                                return
                            if r.status_code in (429, 500, 502, 503, 504):
                                raise RuntimeError(f"HTTP {r.status_code}")
                            return
                        except Exception:
                            if attempt == 3:
                                return
                            await asyncio.sleep(backoff)
                            backoff *= 2
                finally:
                    pbar.update(1)

            await asyncio.gather(*[fetch_one(t, url, out) for (t, url, out) in tasks])
            pbar.close()

    import asyncio

    asyncio.run(runner())


def _ensure_fonts(font_dir: Path, timeout_s: float = 30.0) -> List[Dict[str, str]]:
    print("[1/6] Checking fonts...")
    font_dir.mkdir(parents=True, exist_ok=True)
    missing = [spec for spec in FONT_SPECS if not (font_dir / spec.filename).exists()]
    if missing:
        print(f"[2/6] Downloading missing fonts ({len(missing)})...")
        pbar = tqdm(total=len(missing), desc="Downloading fonts", unit="font")
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            for spec in missing:
                ok = False
                backoff = 1.0
                for attempt in range(4):
                    try:
                        resp = client.get(spec.url, headers={"User-Agent": "tweetpdf-standard/1.0"})
                        if resp.status_code == 200 and resp.content:
                            (font_dir / spec.filename).write_bytes(resp.content)
                            ok = True
                            break
                        if resp.status_code in (429, 500, 502, 503, 504):
                            raise RuntimeError(f"HTTP {resp.status_code}")
                        break
                    except Exception:
                        if attempt == 3:
                            break
                        import time

                        time.sleep(backoff)
                        backoff *= 2
                pbar.update(1)
                if not ok:
                    pbar.close()
                    raise SystemExit(f"Failed to download font: {spec.filename}")
        pbar.close()
    else:
        print("[2/6] Fonts already present.")

    return [
        {
            "family": spec.family,
            "src": (font_dir / spec.filename).resolve().as_uri(),
            "format": spec.format_hint,
        }
        for spec in FONT_SPECS
    ]


def _render_pdf(rows: Sequence[TweetRow], out_pdf: Path, template_dir: Path, font_faces: Sequence[Dict[str, str]]) -> None:
    print("[5/6] Rendering PDF...")
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape(["html", "xml"]))
    tpl = env.get_template("template.html")
    html_str = tpl.render(
        title="Tweet Export (Standard)",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        rows=rows,
        font_faces=font_faces,
    )
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise SystemExit("Cannot import weasyprint. Install requirements and retry.") from exc
    HTML(string=html_str, base_url=str(template_dir.resolve())).write_pdf(str(out_pdf))


def _format_size(total_bytes: int) -> str:
    if total_bytes >= 1024 ** 3:
        return f"{total_bytes / (1024 ** 3):.2f} GB"
    return f"{total_bytes / (1024 ** 2):.2f} MB"


def _remove_cache(cache_root: Path) -> Tuple[int, int]:
    if not cache_root.exists():
        return 0, 0
    files = 0
    bytes_total = 0
    for p in cache_root.rglob("*"):
        if p.is_file():
            files += 1
            try:
                bytes_total += p.stat().st_size
            except OSError:
                pass
    shutil.rmtree(cache_root, ignore_errors=True)
    return files, bytes_total


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Standard edition: TwExport CSV -> PDF (date | content)")
    ap.add_argument("--csv", help="Input CSV path")
    ap.add_argument("--out", default=None, help="Output PDF path (default: same name as CSV)")
    ap.add_argument("--start", default=None, help="Date range start (YYYY-MM-DD)")
    ap.add_argument("--end", default=None, help="Date range end (YYYY-MM-DD)")
    ap.add_argument("--sort", choices=("asc", "desc"), default="asc", help="Sort by date")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Concurrent media downloads")
    ap.add_argument("--allow-hosts", default=",".join(DEFAULT_ALLOW_HOSTS), help="Comma-separated host allowlist")
    ap.add_argument("--download-dir", default=".tweetpdf_cache", help="Temporary media cache directory")
    ap.add_argument("--init", action="store_true", help="Initialize fonts/resources and exit")
    ap.add_argument("--version", action="store_true", help="Show version and exit")
    return ap.parse_args()


def main() -> None:
    args = _parse_args()
    _print_banner()

    if args.version:
        print(f"ExportTweetsToPDF-Sdanderd version {VERSION}")
        return

    root_dir = Path(__file__).parent.resolve()
    font_dir = root_dir / "fonts"
    template_dir = root_dir / "templates"

    if args.init:
        _ensure_fonts(font_dir)
        print("Init complete: fonts and templates are ready.")
        return

    if not args.csv:
        raise SystemExit("Missing required argument: --csv")

    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")

    start_d, end_d = _parse_date_range(args.start, args.end)
    csv_path = Path(args.csv).expanduser().resolve()
    out_pdf = Path(args.out).expanduser().resolve() if args.out else csv_path.with_suffix(".pdf")
    cache_root = Path(args.download_dir).expanduser().resolve()
    media_cache = cache_root / "media"
    allow_hosts = [h.strip() for h in str(args.allow_hosts).split(",") if h.strip()]
    font_faces = _ensure_fonts(font_dir)

    print("[3/6] Reading CSV and preparing rows...")
    rows = _read_rows(csv_path)
    rows = _filter_rows(rows, start_d, end_d)
    rows.sort(key=lambda r: r.created_at, reverse=(args.sort == "desc"))
    for t in rows:
        t.text_html = _text_to_html(t.text)
    print(f"Tweets in output scope: {len(rows)}")

    _download_media(
        rows=rows,
        media_cache_dir=media_cache,
        allow_hosts=allow_hosts,
        concurrency=args.concurrency,
    )

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    _render_pdf(rows=rows, out_pdf=out_pdf, template_dir=template_dir, font_faces=font_faces)

    print("[6/6] Cleaning cache...")
    removed_files, removed_bytes = _remove_cache(cache_root)
    print(f"Cache cleaned: removed {removed_files} files, freed {_format_size(removed_bytes)}")
    print(f"OK: wrote {out_pdf}")


if __name__ == "__main__":
    main()
