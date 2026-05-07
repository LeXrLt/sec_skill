---
name: sec-edgar-fetch
description: >
  Fetch the latest SEC EDGAR filings. The user can request a specific number
  of recent filings (e.g. "查一下SEC上最近的100条记录", "Fetch the latest 50
  SEC filings"). The skill scrapes the SEC EDGAR RSS feed, downloads all
  associated documents (HTML, XML, TXT) for each filing, and saves structured
  JSON output with metadata and file paths.
metadata:
  openclaw:
    emoji: "📊"
    requires:
      bins:
        - python3
---

# SEC EDGAR Filings Fetcher

## When to use this skill

Use this skill when the user asks to:
- Fetch / query / look up recent SEC EDGAR filings
- 查 SEC / EDGAR 上的最新提交记录
- Download SEC filing documents
- Get the latest SEC submissions

## How to use

1. **Extract the count** from the user's message. If the user says a number
   (e.g. "100条", "50 filings", "最近200条"), use that as `COUNT`. If no
   number is specified, default to `100`.

2. **Run the scraper** from the project directory `{baseDir}`:

   ```bash
   cd {baseDir} && .venv/bin/python main.py --count COUNT
   ```

   Replace `COUNT` with the actual number.

3. **Report the results** to the user:
   - The JSON output file is saved under `{baseDir}/output/edgar_filings_<timestamp>.json`.
   - Downloaded filing documents are organized under `{baseDir}/output/filings/<AccNo>/`.
   - Each entry in the JSON contains `title`, `link`, `category`, `author`,
     `updated`, `summary`, and a `documents` dict with paths to downloaded files.

## Examples

| User says | Command |
|---|---|
| 查一下SEC上最近的100条记录 | `.venv/bin/python main.py --count 100` |
| Fetch the latest 50 SEC filings | `.venv/bin/python main.py --count 50` |
| 帮我爬取SEC EDGAR最新的200条提交 | `.venv/bin/python main.py --count 200` |
| 看看SEC最近有什么提交 | `.venv/bin/python main.py --count 100` |

## Output format

The JSON file contains an array of filing records:

```json
{
  "title": "4 - Company Name (CIK) (Reporting)",
  "link": "https://www.sec.gov/Archives/edgar/data/.../index.htm",
  "summary": "Filed: 2026-05-01 AccNo: ...",
  "updated": "2026-05-01T22:00:00-04:00",
  "category": "4",
  "author": "",
  "documents": {
    "html": "output/filings/<AccNo>/form4.html",
    "xml": "output/filings/<AccNo>/form4.xml",
    "txt": "output/filings/<AccNo>/<AccNo>.txt"
  }
}
```

## Notes

- SEC limits each RSS page to 100 entries max; the script automatically
  paginates to fetch the requested total.
- The script includes retry logic (3 attempts) and rate-limiting delays
  to avoid being blocked by SEC servers.
- The `output/` directory is NOT cleared automatically between runs;
  existing files are skipped if already downloaded.
