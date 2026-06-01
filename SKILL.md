---
name: sec-edgar-query
description: Query SEC EDGAR filings stored in the local PostgreSQL database using natural language. Search filings by company, CIK, filing type, keyword, or date range; list companies; and view statistics. Read-only — no data modification.
metadata:
  openclaw:
    emoji: "📊"
    requires:
      bins:
        - python3
---

# SEC EDGAR Database Query Skill

This skill answers natural-language questions about SEC EDGAR filings that have
been previously crawled and stored in a PostgreSQL database (`sec_edgar_filings` table).

**This skill is strictly read-only. It never inserts, updates, or deletes any data.**

## When to use

Use this skill when the user wants to:
- Read or search SEC EDGAR filings from the database
- List companies / CIKs that have been crawled
- Find filings by company name, CIK, filing type, keyword, or date range
- View the full summary of a specific filing
- Get statistics on crawled SEC filings

Do **NOT** use this skill when the user wants to crawl/download new filings from
SEC EDGAR (that is the crawler workflow in `main.py`).

If the database is not yet set up (no `.venv/` or `.env`, or connection errors),
run the **`sec-edgar-setup`** skill (`SKILL_SETUP.md`) first.

## How to use

Translate the user's natural-language request into one of the commands below.
All commands share the same base invocation:

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py <command> [options]
```

### 1. List companies

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py companies
```

Returns every company/CIK that has filings, with counts and date ranges.

### 2. Query filings

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py filings [options]
```

Options:
- `--cik CIK` — Filter by exact CIK
- `--company NAME` — Filter by company name (fuzzy, case-insensitive)
- `--type TYPE` — Filter by filing type (e.g. `4`, `8-K`, `10-K`)
- `--search KEYWORD` — Search in title and summary (case-insensitive)
- `--since YYYY-MM-DD` — Start date (inclusive)
- `--until YYYY-MM-DD` — End date (inclusive)
- `--limit N` — Max results (default: 20, max: 500)
- `--offset N` — Skip first N results (for pagination)
- `--id ID` — Fetch a single filing by its database ID
- `--full` — Show complete summary instead of preview

### 3. View statistics

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py stats [--cik CIK]
```

Returns total filings, distinct company count, and counts by filing type with date ranges.

## Output format

Each filing is output in a stable structured format:

```
ID: <id>
标题: <title>
来源: sec_edgar
类型: <filing_type>
公司: <company_name>
CIK: <cik>
提交编号: <accession_no>
提交时间: <filed_at>
原始链接: <index_url>
状态: <status>
本地文件: <local document paths>   (if present)
摘要预览: <first 200 chars>        (default)
--- 摘要 ---                       (with --full flag)
<full summary>
```

Filings are separated by `============` lines.

## Examples

User says: "看看数据库里有哪些公司提交了SEC文件"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py companies`

User says: "搜索SEC里关于merger的提交"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py filings --search merger`

User says: "查一下CIK 0000320193 最近10条提交"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py filings --cik 0000320193 --limit 10`

User says: "查 Apple 公司的 8-K 文件"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py filings --company Apple --type 8-K`

User says: "查看ID为42的提交全文"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py filings --id 42 --full`

User says: "2026年1月到3月的所有提交"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py filings --since 2026-01-01 --until 2026-03-31`

User says: "SEC数据库里有多少提交记录"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py stats`

## Setup

This skill shares the virtual environment and `.env` with the SEC crawler.
If the environment is missing, run the `sec-edgar-setup` skill (`SKILL_SETUP.md`).
Database connection is configured via `{baseDir}/.env` (read-only user).
