#!/usr/bin/env python3
"""Scrape JanitorAI profile HTML and CSS into a local output folder."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
}


def fetch_html(url: str, use_browser: bool = False) -> str:
    if use_browser:
        return fetch_html_with_playwright(url)

    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def fetch_html_with_playwright(url: str) -> str:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Install it with `pip install playwright` and `playwright install chromium`."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 2200},
            user_agent=DEFAULT_HEADERS["User-Agent"],
        )
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()
        return html


def extract_profile_metadata(soup: BeautifulSoup) -> dict:
    title = soup.title.get_text(strip=True) if soup.title else ""
    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta_tag:
        meta_description = meta_tag.get("content", "")

    h1 = soup.find("h1")
    h2 = soup.find("h2")
    profile_name = h1.get_text(" ", strip=True) if h1 else ""
    if not profile_name and h2:
        profile_name = h2.get_text(" ", strip=True)

    return {
        "title": title,
        "meta_description": meta_description,
        "profile_name": profile_name,
    }


def collect_inline_css(soup: BeautifulSoup) -> list[str]:
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


def collect_stylesheet_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []
    for link in soup.find_all("link"):
        rel = link.get("rel", [])
        if isinstance(rel, str):
            rel_values = [rel]
        else:
            rel_values = rel

        href = link.get("href")
        if href and "stylesheet" in rel_values:
            urls.append(urljoin(base_url, href))

    # Remove duplicates while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for item in urls:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def download_stylesheets(urls: Iterable[str]) -> list[tuple[str, str]]:
    css_payloads: list[tuple[str, str]] = []
    for url in urls:
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
            if response.status_code != 200:
                continue
            content_type = response.headers.get("Content-Type", "")
            if "css" not in content_type and not url.lower().endswith(".css"):
                continue
            css_payloads.append((url, response.text))
        except requests.RequestException:
            continue
    return css_payloads


def save_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_summary(profile_name: str, metadata: dict, css_count: int, stylesheet_count: int) -> dict:
    return {
        "profile_name": profile_name,
        "title": metadata.get("title", ""),
        "meta_description": metadata.get("meta_description", ""),
        "inline_css_blocks": css_count,
        "stylesheet_links": stylesheet_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape a JanitorAI profile page into HTML and CSS files.")
    parser.add_argument("--url", required=True, help="The JanitorAI profile URL to scrape.")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where the scraped HTML/CSS files will be saved.",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Use Playwright to render the page before scraping. Helpful for JS-heavy pages.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    css_dir = output_dir / "css"
    css_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_html = fetch_html(args.url, use_browser=args.browser)
    except Exception as exc:  # pragma: no cover
        print(f"Failed to fetch the page: {exc}")
        return 1

    soup = BeautifulSoup(raw_html, "lxml")
    metadata = extract_profile_metadata(soup)

    inline_css = collect_inline_css(soup)
    stylesheet_urls = collect_stylesheet_urls(soup, args.url)
    downloaded_css = download_stylesheets(stylesheet_urls)

    merged_css = []
    for css_block in inline_css:
        merged_css.append(css_block)

    for _, css_text in downloaded_css:
        if css_text not in merged_css:
            merged_css.append(css_text)

    save_file(output_dir / "profile.html", raw_html)

    final_css = "\n\n".join(merged_css)
    save_file(output_dir / "profile.css", final_css)

    for index, (stylesheet_url, css_text) in enumerate(downloaded_css, start=1):
        save_file(css_dir / f"stylesheet_{index}.css", css_text)

    summary = build_summary(
        metadata.get("profile_name", ""),
        metadata,
        len(inline_css),
        len(stylesheet_urls),
    )
    save_file(output_dir / "profile_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"Scraped HTML saved to: {output_dir / 'profile.html'}")
    print(f"Scraped CSS saved to: {output_dir / 'profile.css'}")
    print(f"Profile summary saved to: {output_dir / 'profile_summary.json'}")
    print(f"Found {len(stylesheet_urls)} stylesheet URLs and {len(inline_css)} inline CSS blocks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
