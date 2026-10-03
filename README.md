# JanitorAI Profile CSS + HTML Scraper

A lightweight scraper that grabs a JanitorAI profile page, extracts the page HTML, collects internal CSS and linked stylesheet content, and saves the results to an output directory.

This is useful for:
- auditing profile markup
- collecting inline and external CSS
- exporting profile layouts for analysis
- building local copies of a profile page for debugging

## Features

- Fetches a profile page using a browser-like user-agent
- Extracts raw HTML from the page
- Collects inline `<style>` blocks and `style=` attributes
- Follows linked stylesheet URLs and saves their CSS
- Stores metadata such as title, meta description, and common profile headings
- Writes a simple JSON summary alongside the HTML/CSS exports

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python janitorai_scraper.py --url "https://janitorai.com/profile/your-profile" --output-dir output
```

Optional:

```bash
python janitorai_scraper.py --url "https://janitorai.com/profile/your-profile" --output-dir output --browser
```

The `--browser` mode tries to render the page using Playwright, which can help when the profile is assembled dynamically with JavaScript.

## Output

The scraper creates a directory like this:

```text
output/
├── profile.html
├── profile.css
├── profile_summary.json
└── css/
    └── stylesheet_1.css
```

## Notes

- Respect the target site's robots and terms of service.
- Some profile pages are rendered client-side, so a browser-based fetch may be required.
- The script intentionally focuses on static extraction without mutating or posting data.
