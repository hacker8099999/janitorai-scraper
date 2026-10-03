# JanitorAI Profile CSS + HTML Scraper

A robust, zero-config scraper for extracting any JanitorAI profile's HTML and CSS. Just paste a profile URL and it works!

## Features

✨ **Zero-config usage** — Just paste a profile URL  
🌐 **HTTP + Browser modes** — Works with static and JavaScript-rendered profiles  
🎨 **Full CSS extraction** — Inline styles, linked stylesheets, and `@import` chains  
🔐 **Cookie support** — Handle authenticated profiles  
📊 **Metadata extraction** — Profile name, title, description, ID  
📁 **Organized output** — HTML, CSS, and summary in one folder  

## Installation

```bash
git clone https://github.com/hacker8099999/janitorai-scraper.git
cd janitorai-scraper
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Optional: Browser rendering

If you want to scrape JavaScript-heavy profiles:

```bash
python -m playwright install chromium
```

## Quick Start

```bash
python janitorai_scraper.py --url "https://janitorai.com/profile/username"
```

That's it! Files will be saved to `output/`.

## Usage Examples

### Basic HTTP scrape (fast)

```bash
python janitorai_scraper.py --url "https://janitorai.com/profile/alice"
```

### Browser rendering (handles JavaScript)

```bash
python janitorai_scraper.py --url "https://janitorai.com/profile/alice" --browser
```

### Custom output directory

```bash
python janitorai_scraper.py --url "https://janitorai.com/profile/alice" --output-dir my_export
```

### With authentication cookies

```bash
python janitorai_scraper.py \
  --url "https://janitorai.com/profile/alice" \
  --browser \
  --cookies "sessionid=abc123; csrftoken=xyz456"
```

### JSON cookies

```bash
python janitorai_scraper.py \
  --url "https://janitorai.com/profile/alice" \
  --cookies '{"sessionid":"abc123","auth_token":"xyz456"}'
```

### Wait for specific element (browser mode)

```bash
python janitorai_scraper.py \
  --url "https://janitorai.com/profile/alice" \
  --browser \
  --wait-for-selector "[data-testid='profile-loaded']"
```

## Output

```
output/
├── profile.html              # Full page HTML
├── profile.css               # All CSS merged together
├── profile_summary.json      # Metadata and stats
└── css/
    ├── stylesheet_1.css      # External stylesheet 1
    └── stylesheet_2.css      # External stylesheet 2
```

### Example summary.json

```json
{
  "url": "https://janitorai.com/profile/alice",
  "profile_id": "alice",
  "profile_name": "Alice's Amazing Profile",
  "title": "Alice | JanitorAI",
  "meta_description": "Check out Alice's JanitorAI profile",
  "inline_css_blocks": 12,
  "stylesheet_links": 3
}
```

## When to Use Each Mode

| Mode | Speed | Best for |
|------|-------|----------|
| **HTTP (default)** | Fast ⚡ | Static profiles, quick export |
| **Browser `--browser`** | Slower 🔄 | Dynamic content, interactive elements, JavaScript |

## Troubleshooting

### "Playwright is not installed"

```bash
python -m playwright install chromium
```

### Empty or incomplete profile

Try browser mode:

```bash
python janitorai_scraper.py --url "..." --browser
```

### 403/401 Errors

The profile requires authentication. Extract cookies from your browser and pass them:

```bash
python janitorai_scraper.py --url "..." --cookies "sessionid=..."
```

### No CSS being captured

Some JanitorAI profiles use CSS-in-JS or dynamic styling. Use `--browser` mode for the best results.

## Command-line Arguments

```
--url URL                    JanitorAI profile URL (required)
--output-dir DIR            Output directory (default: output)
--browser                   Use Playwright for rendering (recommended)
--wait-for-selector SEL     CSS selector to wait for in browser mode
--cookies COOKIES           Auth cookies as JSON or key=value pairs
--no-verify                 Skip URL verification
```

## Notes

- **Respect ToS**: Make sure your usage complies with JanitorAI's terms of service.
- **Rate limiting**: The scraper respects timeouts and won't hammer the server.
- **Privacy**: Only scrape profiles you have permission to access.
- **Local profiles**: Works with `localhost:3000` for local JanitorAI development.

## License

MIT
