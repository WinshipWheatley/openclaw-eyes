"""
chief_website_qa.py

Crawls deeppocketrecords.com after every update. Checks broken links,
missing meta tags, slow pages, images without alt text. Checks SEO
for Winship and Fundo keyword tracks separately. Checks brand consistency.
Reports pass/fail list before anything goes live.

Domain: deeppocketrecords.com (registered on Namecheap)
Fundo teaser page is the first test target.

Triggered by:
  - "website qa" / "qa report" / "check the site" / "site audit"
  - "qa fundo" (targets Fundo teaser page specifically)
Intent: website_qa in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/openclaw-vault/Website/QA Log.md
"""

import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

try:
    import requests
    from bs4 import BeautifulSoup
    _CRAWL_AVAILABLE = True
except ImportError:
    _CRAWL_AVAILABLE = False

# ── Config ───────────────────────────────────────────────────────────────────────

BASE_URL      = "https://deeppocketrecords.com"
FUNDO_URL     = "https://deeppocketrecords.com/fundo"
MAX_PAGES     = 10
SLOW_THRESHOLD_S = 3.0

VAULT_WEB_DIR = Path("/mnt/c/OpenClawShared/openclaw-vault/Website")
QA_LOG_MD     = VAULT_WEB_DIR / "QA Log.md"

# ── Keyword tracks ───────────────────────────────────────────────────────────────

WINSHIP_KEYWORDS = [
    "winship wheatley",
    "deep pocket records",
    "annapolis",
    "deeppocketrecords.com",
]

FUNDO_KEYWORDS = [
    "fundo",
    "electronic",
    "anonymous",
]

# ── Brand markers (check for DPR tone on DPR pages) ─────────────────────────────

DPR_BRAND_MARKERS   = ["deep pocket records", "winship", "annapolis"]
FUNDO_BRAND_MARKERS = ["fundo"]

# ── Per-page check result ────────────────────────────────────────────────────────

class PageResult:
    def __init__(self, url: str):
        self.url      = url
        self.checks:  list[tuple[str, bool, str]] = []  # (check_name, passed, detail)
        self.load_ms: float = 0.0
        self.offline: bool  = False

    def add(self, name: str, passed: bool, detail: str = ""):
        self.checks.append((name, passed, detail))

    def passed_count(self) -> int:
        return sum(1 for _, p, _ in self.checks if p)

    def failed_count(self) -> int:
        return sum(1 for _, p, _ in self.checks if not p)


# ── Crawler ──────────────────────────────────────────────────────────────────────

def _fetch_page(url: str) -> tuple[int, float, str]:
    """Return (status_code, load_seconds, html). status_code=0 on error."""
    try:
        start    = time.time()
        response = requests.get(url, timeout=10, allow_redirects=True, headers={
            "User-Agent": "OpenClaw-QA/1.0 (deeppocketrecords.com site audit)"
        })
        elapsed  = time.time() - start
        return response.status_code, elapsed, response.text
    except requests.RequestException:
        return 0, 0.0, ""


def _check_page(url: str, is_fundo: bool = False) -> PageResult:
    result = PageResult(url)
    status, elapsed, html = _fetch_page(url)
    result.load_ms = elapsed

    if status == 0:
        result.offline = True
        result.add("HTTP reachable", False, "Site could not be reached")
        return result

    result.add("HTTP status", status == 200, f"HTTP {status}")
    result.add("Load time < 3s", elapsed < SLOW_THRESHOLD_S, f"{elapsed:.2f}s")

    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("title")
    result.add("Title tag present", bool(title_tag and title_tag.string),
               title_tag.string.strip()[:60] if title_tag and title_tag.string else "MISSING")

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_content = (meta_desc or {}).get("content", "") if meta_desc else ""
    result.add("Meta description", bool(desc_content),
               desc_content[:80] if desc_content else "MISSING")

    # OG tags
    og_title = soup.find("meta", property="og:title")
    og_image = soup.find("meta", property="og:image")
    result.add("og:title", bool(og_title), "present" if og_title else "MISSING")
    result.add("og:image", bool(og_image), "present" if og_image else "MISSING")

    # H1
    h1_tags = soup.find_all("h1")
    result.add("H1 present", bool(h1_tags),
               h1_tags[0].get_text()[:60] if h1_tags else "MISSING")
    result.add("Single H1", len(h1_tags) <= 1,
               f"{len(h1_tags)} H1 tags found")

    # Canonical
    canonical = soup.find("link", rel="canonical")
    result.add("Canonical tag", bool(canonical),
               canonical.get("href", "")[:60] if canonical else "MISSING")

    # Images without alt
    images    = soup.find_all("img")
    no_alt    = [img for img in images if not img.get("alt")]
    result.add("All images have alt text", len(no_alt) == 0,
               f"{len(no_alt)} of {len(images)} images missing alt")

    # Keyword check
    body_text = soup.get_text().lower()
    if is_fundo:
        for kw in FUNDO_KEYWORDS:
            result.add(f"Fundo keyword: '{kw}'", kw in body_text)
        for marker in FUNDO_BRAND_MARKERS:
            result.add(f"Fundo brand marker: '{marker}'", marker in body_text)
    else:
        for kw in WINSHIP_KEYWORDS:
            result.add(f"DPR keyword: '{kw}'", kw in body_text)
        for marker in DPR_BRAND_MARKERS:
            result.add(f"DPR brand marker: '{marker}'", marker in body_text)

    # Internal link discovery (for full crawl)
    result._links = [
        urljoin(url, a["href"])
        for a in soup.find_all("a", href=True)
        if urlparse(urljoin(url, a["href"])).netloc == urlparse(url).netloc
    ]

    return result


def _collect_internal_links(start_url: str, html: str) -> list[str]:
    soup  = BeautifulSoup(html, "html.parser")
    base  = urlparse(start_url).netloc
    links = set()
    for a in soup.find_all("a", href=True):
        full = urljoin(start_url, a["href"])
        if urlparse(full).netloc == base:
            links.add(full.split("#")[0].split("?")[0])
    links.discard(start_url)
    return list(links)[:MAX_PAGES - 1]


def _run_crawl(target_url: str, fundo_only: bool = False) -> list[PageResult]:
    results  = []
    is_fundo = "fundo" in target_url.lower()

    # Fetch and check the target URL
    primary = _check_page(target_url, is_fundo=is_fundo)
    results.append(primary)

    if primary.offline or fundo_only:
        return results

    # Crawl discovered internal links (non-fundo pages use DPR keyword checks)
    _, _, html = _fetch_page(target_url)
    if html:
        sub_urls = _collect_internal_links(target_url, html)
        for url in sub_urls[:MAX_PAGES - 1]:
            results.append(_check_page(url, is_fundo=("fundo" in url.lower())))

    return results


# ── Brand analysis ───────────────────────────────────────────────────────────────

_BRAND_PROMPT = """\
You are the QA reviewer for deeppocketrecords.com.
You just crawled the site and here is a summary of what was found on the pages:

{page_summaries}

Based on this, answer two questions in 3-4 sentences each:
1. BRAND CHECK — Does the content feel like Deep Pocket Records? Sophisticated, cinematic,
   no clichés? Or does it feel generic?
2. NEXT ACTIONS — What are the top 2 most important fixes based on these results?

Return plain text only. Use "BRAND CHECK:" and "NEXT ACTIONS:" as section headers."""


def _brand_analysis(results: list[PageResult]) -> str:
    summaries = []
    for r in results:
        status = "OFFLINE" if r.offline else f"{r.passed_count()} passed / {r.failed_count()} failed"
        summaries.append(f"URL: {r.url} — {status}")
        for name, passed, detail in r.checks:
            icon = "✓" if passed else "✗"
            summaries.append(f"  {icon} {name}: {detail}")
    summaries_text = "\n".join(summaries)

    result = _local_model_call(
        _BRAND_PROMPT.format(page_summaries=summaries_text),
        timeout=30,
        task_class="chief_evidence_synthesis",
    )
    if not result:
        total_failed = sum(r.failed_count() for r in results)
        return f"BRAND CHECK: LLM Unavailable.\nNEXT ACTIONS: Manually review the {total_failed} failed QA checks."
    return result


# ── Report formatter ─────────────────────────────────────────────────────────────

def _format_report(results: list[PageResult], brand_analysis: str) -> str:
    lines = [f"QA Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]

    total_pass = sum(r.passed_count() for r in results)
    total_fail = sum(r.failed_count() for r in results)
    offline    = any(r.offline for r in results)

    if offline:
        lines.append("⚠️  SITE OFFLINE — Could not reach deeppocketrecords.com\n")
    else:
        lines.append(f"Overall: {total_pass} passed · {total_fail} failed\n")

    for r in results:
        lines.append(f"\n{'─' * 50}")
        lines.append(f"Page: {r.url}  ({r.load_ms:.2f}s)")
        if r.offline:
            lines.append("  STATUS: OFFLINE")
            continue
        for name, passed, detail in r.checks:
            icon = "✅" if passed else "❌"
            detail_str = f" — {detail}" if detail else ""
            lines.append(f"  {icon} {name}{detail_str}")

    if not offline:
        lines.append(f"\n{'─' * 50}")
        lines.append("\nBrand Analysis:\n")
        lines.append(brand_analysis)

    return "\n".join(lines)


def _write_qa_log(report: str) -> None:
    VAULT_WEB_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry     = f"\n## {timestamp}\n\n```\n{report}\n```\n\n---"
    existing  = QA_LOG_MD.read_text(encoding="utf-8") if QA_LOG_MD.exists() else (
        "---\ntype: qa-log\n---\n\n# Website QA Log\n\n"
        "_Generated by `chief_website_qa.py`_\n"
    )
    QA_LOG_MD.write_text(existing + entry, encoding="utf-8")


# ── Public entry point ────────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if not _CRAWL_AVAILABLE:
        return ["QA brain requires 'requests' and 'beautifulsoup4'. Run: pip install requests beautifulsoup4"]

    # Determine target
    fundo_only = "fundo" in t
    target     = FUNDO_URL if fundo_only else BASE_URL

    results        = _run_crawl(target, fundo_only=fundo_only)
    brand_analysis = _brand_analysis(results)
    report         = _format_report(results, brand_analysis)

    _write_qa_log(report)

    # Truncate for Telegram if very long
    if len(report) > 3000:
        short = report[:2800] + "\n\n... (full report saved to QA Log.md)"
        return [short]
    return [report]


# ── CLI ───────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "website qa"
    print(f"Running website QA brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nQA Log: {QA_LOG_MD}")
