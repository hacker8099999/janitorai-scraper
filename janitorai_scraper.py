#!/usr/bin/env python3
"""Scrape a JanitorAI profile page into a local HTML/CSS export."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://janitorai.com/",
}

# JanitorAI-specific selectors and patterns
JANITORAI_DOMAIN_PATTERNS = [
    r"janitorai\.com",
    r"localhost:3000",  # local dev
]

JANITORAI_PROFILE_SELECTORS = [
    "[data-testid='profile-container']",
    "[class*='profile']",
    ".profile-card",
    "main",
    "[role='main']",
]

JANITORAI_WAIT_SELECTORS = [
    "[data-testid='profile-container']",
    "[class*='profile']",
    "h1",
    ".profile-name",
]


def is_janitorai_url(url: str) -> bool:
    """Check if the given URL belongs to JanitorAI."""
    for pattern in JANITORAI_DOMAIN_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def parse_cookie_string(raw: str | None) -> dict[str, str]:
    """Parse cookies from string or JSON format."""
    if not raw:
        return {}

    if raw.strip().startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass

    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def build_requests_session(cookies: dict[str, str] | None = None) -> requests.Session:
    """Build a requests session with default headers and cookies."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if cookies:
        session.cookies.update(cookies)
    return session


def fetch_html(
    url: str,
    use_browser: bool = False,
    cookies: dict[str, str] | None = None,
    wait_for_selector: str | None = None,
) -> str:
    """Fetch HTML from the given URL."""
    if use_browser:
        return fetch_html_with_playwright(url, cookies=cookies, wait_for_selector=wait_for_selector)

    session = build_requests_session(cookies)
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_html_with_playwright(
    url: str,
    cookies: dict[str, str] | None = None,
    wait_for_selector: str | None = None,
) -> str:
    """Fetch HTML using Playwright for JavaScript rendering."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Install it with: pip install playwright && playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=DEFAULT_HEADERS["User-Agent"])
        if cookies:
            context.add_cookies(
                [{"name": k, "value": v, "url": url} for k, v in cookies.items()]
            )
        page = context.new_page(viewport={"width": 1440, "height": 2200})
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for profile-specific selector if provided or use default
        selector_to_wait = wait_for_selector or find_wait_selector(page)
        if selector_to_wait:
            try:
                page.wait_for_selector(selector_to_wait, timeout=30000)
            except Exception:
                # If selector doesn't appear, just continue with what we have
                pass
        
        html = page.content()
        browser.close()
        return html


def find_wait_selector(page: Any) -> str | None:
    """Try to find a suitable wait selector from JanitorAI defaults."""
    for selector in JANITORAI_WAIT_SELECTORS:
        try:
            if page.query_selector(selector):
                return selector
        except Exception:
            continue
    return None


def extract_profile_metadata(soup: BeautifulSoup, url: str) -> dict[str, str]:
    """Extract metadata from the profile page."""
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    description_tag = (
        soup.find("meta", attrs={"name": "description"})
        or soup.find("meta", attrs={"property": "og:description"})
        or soup.find("meta", attrs={"name": "twitter:description"})
    )
    description = description_tag.get("content", "") if description_tag else ""

    # Try to find profile name from various selectors
    profile_name = ""
    for selector in ["h1", "h2", "[class*='name']", "[class*='title']"]:
        heading = soup.select_one(selector)
        if heading:
            profile_name = heading.get_text(" ", strip=True)
            if profile_name:
                break

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and not profile_name:
        profile_name = og_title.get("content", "")

    # Extract profile ID from URL if possible
    profile_id = ""
    url_match = re.search(r"/profile/([^/?]+)", url)
    if url_match:
        profile_id = url_match.group(1)

    return {
        "title": title,
        "meta_description": description,
        "profile_name": profile_name,
        "profile_id": profile_id,
        "url": url,
    }


def collect_inline_css(soup: BeautifulSoup) -> list[str]:
    """Collect all inline CSS from <style> tags and style attributes."""
    css_blocks: list[str] = []

    for style_tag in soup.find_all("style"):
        content = style_tag.get_text(strip=True)
        if content:
            css_blocks.append(content)

    for tag in soup.find_all(True):
        style_attr = tag.get("style")
        if style_attr:
            css_blocks.append(style_attr.strip())

    return css_blocks


def dedupe(items: Iterable[str]) -> list[str]:
    """Deduplicate items while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def collect_stylesheet_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Collect all external stylesheet URLs."""
    stylesheets: list[str] = []
    for tag in soup.find_all("link"):
        rel_values = tag.get("rel", [])
        if isinstance(rel_values, str):
            rel_values = [rel_values]
        href = tag.get("href")
        if href and "stylesheet" in rel_values:
            stylesheets.append(urljoin(base_url, href))
    return dedupe(stylesheets)


def resolve_css_imports(session: requests.Session, css_text: str, base_url: str) -> list[str]:
    """Resolve @import URLs in CSS."""
    imports: list[str] = []
    pattern = r'@import\s+(?:url\()?["\']?([^"\')]+)["\']?\)?'
    for match in re.finditer(pattern, css_text, flags=re.IGNORECASE):
        imported_url = match.group(1)
        if imported_url.startswith("data:"):
            continue
        imports.append(urljoin(base_url, imported_url))
    return dedupe(imports)


def collect_css_assets(session: requests.Session, soup: BeautifulSoup, base_url: str) -> list[str]:
    """Collect all CSS blocks from inline styles and stylesheets."""
    css_blocks = collect_inline_css(soup)
    stylesheet_urls = collect_stylesheet_urls(soup, base_url)

    for stylesheet_url in stylesheet_urls:
        try:
            response = session.get(stylesheet_url, timeout=30)
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        css_text = response.text
        if css_text:
            css_blocks.append(css_text)

        # Try to resolve @import statements
        for imported in resolve_css_imports(session, css_text, stylesheet_url):
            try:
                imported_response = session.get(imported, timeout=30)
            except requests.RequestException:
                continue
            if imported_response.status_code == 200 and imported_response.text:
                css_blocks.append(imported_response.text)

    return dedupe(css_blocks)


def save_text(path: Path, content: str) -> None:
    """Save text content to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_summary(
    url: str,
    metadata: dict[str, str],
    css_block_count: int,
    stylesheet_count: int,
) -> dict[str, Any]:
    """Build a summary of the scraped profile."""
    return {
        "url": url,
        "profile_id": metadata.get("profile_id", ""),
        "profile_name": metadata.get("profile_name", ""),
        "title": metadata.get("title", ""),
        "meta_description": metadata.get("meta_description", ""),
        "inline_css_blocks": css_block_count,
        "stylesheet_links": stylesheet_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape a JanitorAI profile page into HTML/CSS exports. Just paste any JanitorAI profile URL!"
    )
    parser.add_argument("--url", required=True, help="The JanitorAI profile URL to scrape.")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for the scraped HTML, CSS, and summary files.",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Use Playwright to render the page. Recommended for JavaScript-heavy JanitorAI profiles.",
    )
    parser.add_argument(
        "--wait-for-selector",
        default=None,
        help="Optional CSS selector to wait for in browser mode (default: auto-detect).",
    )
    parser.add_argument(
        "--cookies",
        default=None,
        help="Optional cookies as JSON or 'name=value; name=value' format.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification that this is a JanitorAI URL.",
    )
    args = parser.parse_args()

    # Verify the URL is for JanitorAI
    if not args.no_verify and not is_janitorai_url(args.url):
        print(f"⚠️  Warning: {args.url} does not appear to be a JanitorAI URL.")
        print("   Expected a URL matching: janitorai.com/...")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != "y":
            return 1

    output_dir = Path(args.output_dir)
    css_dir = output_dir / "css"
    css_dir.mkdir(parents=True, exist_ok=True)

    cookies = parse_cookie_string(args.cookies)

    print(f"🔍 Fetching profile: {args.url}")
    try:
        raw_html = fetch_html(
            args.url,
            use_browser=args.browser or not args.url.startswith("http"),  # Auto-use browser for localhost
            cookies=cookies,
            wait_for_selector=args.wait_for_selector,
        )
    except Exception as exc:  # pragma: no cover
        print(f"❌ Failed to fetch the profile page: {exc}")
        return 1

    print("📄 Parsing HTML...")
    soup = BeautifulSoup(raw_html, "lxml")
    metadata = extract_profile_metadata(soup, args.url)

    print("🎨 Collecting CSS...")
    session = build_requests_session(cookies)
    css_blocks = collect_css_assets(session, soup, args.url)
    stylesheet_urls = collect_stylesheet_urls(soup, args.url)

    print(f"💾 Saving files to {output_dir}")
    save_text(output_dir / "profile.html", raw_html)
    save_text(output_dir / "profile.css", "\n\n".join(css_blocks))

    for index, stylesheet_url in enumerate(stylesheet_urls, start=1):
        try:
            response = session.get(stylesheet_url, timeout=30)
        except requests.RequestException:
            continue
        if response.status_code == 200 and response.text:
            save_text(css_dir / f"stylesheet_{index}.css", response.text)

    summary = build_summary(
        args.url,
        metadata,
        len(css_blocks),
        len(stylesheet_urls),
    )
    save_text(output_dir / "profile_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"✅ Scrape complete!")
    print(f"   Profile: {metadata.get('profile_name', 'Unknown')}")
    print(f"   HTML: {output_dir / 'profile.html'}")
    print(f"   CSS: {output_dir / 'profile.css'} ({len(css_blocks)} blocks)")
    print(f"   Summary: {output_dir / 'profile_summary.json'}")
    print(f"   Stylesheets: {css_dir} ({len(stylesheet_urls)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
