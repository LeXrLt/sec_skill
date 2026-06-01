"""
SEC EDGAR database query tool (read-only).

Provides CLI access to query the sec_edgar_filings table.
Strictly SELECT-only — no INSERT, UPDATE, or DELETE operations.

Usage:
    python query_db.py companies
    python query_db.py filings [--cik CIK] [--company NAME] [--type TYPE]
                               [--search KEYWORD] [--since DATE] [--until DATE]
                               [--limit N] [--offset N] [--id ID] [--full]
    python query_db.py stats [--cik CIK]
"""

import os
import json
import argparse

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


# Load environment variables from .env (same as crawler)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_db_connection():
    """Create a read-only database connection using .env config (readonly user)."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_READONLY_USER", "hub_readonly"),
        password=os.getenv("POSTGRES_READONLY_PASSWORD", "hub_password"),
        dbname=os.getenv("POSTGRES_DB", "financial_hub"),
    )
    conn.set_session(readonly=True, autocommit=True)
    return conn


# ---------------------------------------------------------------------------
# Output formatting — stable structure for AI Agent consumption
# ---------------------------------------------------------------------------

ITEM_SEPARATOR = "\n" + "=" * 60 + "\n"


def format_company(row: dict) -> str:
    """Format a single company/CIK aggregate record."""
    lines = [
        f"公司: {row.get('company_name') or '(未知)'}",
        f"CIK: {row.get('cik') or ''}",
        f"提交数量: {row.get('cnt', 0)}",
        f"最早提交: {row.get('earliest') or 'N/A'}",
        f"最新提交: {row.get('latest') or 'N/A'}",
    ]
    return "\n".join(lines)


def format_filing(row: dict, full: bool = False) -> str:
    """Format a single filing record in stable output structure."""
    lines = [
        f"ID: {row.get('id')}",
        f"标题: {row.get('title') or '(无标题)'}",
        f"来源: sec_edgar",
        f"类型: {row.get('filing_type') or ''}",
        f"公司: {row.get('company_name') or ''}",
        f"CIK: {row.get('cik') or ''}",
        f"提交编号: {row.get('accession_no') or ''}",
        f"提交时间: {row.get('filed_at') or ''}",
        f"原始链接: {row.get('index_url') or ''}",
        f"状态: {row.get('status') or ''}",
    ]

    # Local document paths (JSONB)
    local_paths = row.get("local_paths") or {}
    if isinstance(local_paths, str):
        try:
            local_paths = json.loads(local_paths)
        except json.JSONDecodeError:
            local_paths = {}
    if local_paths:
        paths = [f"{k}: {v}" for k, v in local_paths.items()]
        lines.append(f"本地文件: {'; '.join(paths)}")

    # Summary
    summary = row.get("summary") or ""
    if full:
        lines.append("")
        lines.append("--- 摘要 ---")
        lines.append(summary if summary else "(无摘要)")
    else:
        preview = summary[:200].replace("\n", " ") if summary else "(无摘要)"
        if len(summary) > 200:
            preview += "..."
        lines.append(f"摘要预览: {preview}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def cmd_companies(conn, args):
    """List all companies/CIKs that have filings."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT company_name, cik,
                   COUNT(*) AS cnt,
                   MIN(filed_at) AS earliest,
                   MAX(filed_at) AS latest
            FROM sec_edgar_filings
            GROUP BY company_name, cik
            ORDER BY cnt DESC
            """
        )
        rows = cur.fetchall()

    if not rows:
        print("没有找到任何公司记录。")
        return

    print(f"共 {len(rows)} 家公司:\n")
    print(ITEM_SEPARATOR.join(format_company(r) for r in rows))


def cmd_filings(conn, args):
    """Query filings with optional filters."""
    conditions = []
    params = []

    if args.cik:
        conditions.append("cik = %s")
        params.append(args.cik)

    if args.company:
        conditions.append("company_name ILIKE %s")
        params.append(f"%{args.company}%")

    if args.type:
        conditions.append("filing_type = %s")
        params.append(args.type)

    if args.search:
        conditions.append("(title ILIKE %s OR summary ILIKE %s)")
        pattern = f"%{args.search}%"
        params.extend([pattern, pattern])

    if args.since:
        conditions.append("filed_at >= %s")
        params.append(args.since)

    if args.until:
        conditions.append("filed_at <= %s")
        params.append(args.until)

    if args.id:
        conditions.append("id = %s")
        params.append(args.id)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    limit = min(args.limit, 500)
    offset = args.offset

    sql = f"""
        SELECT *
        FROM sec_edgar_filings
        {where}
        ORDER BY filed_at DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    query_params = params + [limit, offset]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, query_params)
        rows = cur.fetchall()

    if not rows:
        print("没有找到匹配的提交记录。")
        return

    # Count total matches
    count_sql = f"SELECT COUNT(*) FROM sec_edgar_filings {where}"
    with conn.cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()[0]

    print(f"查询结果: {len(rows)} 条 (共 {total} 条匹配, "
          f"offset={offset}, limit={limit})\n")
    print(ITEM_SEPARATOR.join(format_filing(r, full=args.full) for r in rows))


def cmd_stats(conn, args):
    """Show statistics overview."""
    cik_filter = ""
    params = []
    if args.cik:
        cik_filter = "WHERE cik = %s"
        params = [args.cik]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Distinct company count
        cur.execute(
            f"SELECT COUNT(DISTINCT cik) AS cnt FROM sec_edgar_filings {cik_filter}",
            params,
        )
        company_count = cur.fetchone()["cnt"]

        # Filings by type
        cur.execute(
            f"""
            SELECT filing_type, COUNT(*) AS cnt,
                   MIN(filed_at) AS earliest,
                   MAX(filed_at) AS latest
            FROM sec_edgar_filings
            {cik_filter}
            GROUP BY filing_type
            ORDER BY cnt DESC
            """,
            params,
        )
        type_rows = cur.fetchall()

        # Total filings
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM sec_edgar_filings {cik_filter}",
            params,
        )
        total_filings = cur.fetchone()["cnt"]

    header = "SEC EDGAR 统计概览"
    if args.cik:
        header += f" (CIK: {args.cik})"

    lines = [
        header,
        f"公司总数: {company_count}",
        f"提交总数: {total_filings}",
        "",
        "按提交类型统计:",
    ]
    for r in type_rows:
        lines.append(
            f"  {r['filing_type'] or '(未知)'}: {r['cnt']} 条 "
            f"(最早: {r['earliest'] or 'N/A'}, 最新: {r['latest'] or 'N/A'})"
        )

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SEC EDGAR 数据库只读查询工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- companies ---
    subparsers.add_parser("companies", help="列出所有有提交记录的公司/CIK")

    # --- filings ---
    p_filings = subparsers.add_parser("filings", help="查询提交记录")
    p_filings.add_argument("--cik", type=str, default=None, help="按 CIK 过滤")
    p_filings.add_argument("--company", type=str, default=None, help="按公司名称模糊过滤")
    p_filings.add_argument("--type", type=str, default=None,
                           help="按提交类型过滤 (如 4 / 8-K / 10-K)")
    p_filings.add_argument("--search", type=str, default=None, help="按关键词搜索标题和摘要")
    p_filings.add_argument("--since", type=str, default=None,
                           help="起始日期 (含), 格式 YYYY-MM-DD")
    p_filings.add_argument("--until", type=str, default=None,
                           help="截止日期 (含), 格式 YYYY-MM-DD")
    p_filings.add_argument("--limit", type=int, default=20, help="返回条数上限 (默认 20, 最大 500)")
    p_filings.add_argument("--offset", type=int, default=0, help="跳过前 N 条 (分页用)")
    p_filings.add_argument("--id", type=int, default=None, help="按数据库 ID 精确查询单条")
    p_filings.add_argument("--full", action="store_true", help="显示完整摘要 (默认只显示预览)")

    # --- stats ---
    p_stats = subparsers.add_parser("stats", help="查看统计信息")
    p_stats.add_argument("--cik", type=str, default=None, help="按 CIK 过滤统计")

    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.command == "companies":
            cmd_companies(conn, args)
        elif args.command == "filings":
            cmd_filings(conn, args)
        elif args.command == "stats":
            cmd_stats(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
