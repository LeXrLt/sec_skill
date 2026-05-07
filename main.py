#!/usr/bin/env python3
"""SEC EDGAR 最新提交文件抓取 — 入口脚本"""

import argparse
import sys

from scraper import EdgarScraper


def main():
    parser = argparse.ArgumentParser(description="SEC EDGAR 最新提交文件抓取器")
    parser.add_argument(
        "--count", type=int, default=None,
        help="要抓取的记录总数（默认使用 config.TOTAL_COUNT）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" SEC EDGAR Latest Filings Scraper")
    print("=" * 60)

    scraper = EdgarScraper(total_count=args.count)

    try:
        entries = scraper.run()
    except Exception as e:
        print(f"\n[ERROR] 抓取失败: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[完成] 共获取 {len(entries)} 条提交记录")


if __name__ == "__main__":
    main()
