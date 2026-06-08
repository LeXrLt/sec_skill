#!/usr/bin/env python3
"""SEC EDGAR 最新提交文件抓取 — 入口脚本"""

import argparse
import sys
import time

import psycopg2
from financial_hub_postgres import FinancialHubClient

import config
import db
from scraper import EdgarScraper


def get_db_connection():
    """创建并返回 PostgreSQL 数据库连接。"""
    return psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        dbname=config.POSTGRES_DB,
    )


def main():
    parser = argparse.ArgumentParser(description="SEC EDGAR 最新提交文件抓取器")
    parser.add_argument(
        "--target-id", type=int, default=None,
        help="指定 crawl_target ID（不指定则从数据库查询 sec_edgar 类型的目标）",
    )
    parser.add_argument(
        "-f", "--file-path", type=str, default=None,
        help="指定文件下载位置（默认使用 config.OUTPUT_DIR）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" SEC EDGAR Latest Filings Scraper")
    print("=" * 60)

    # 连接数据库，初始化 FinancialHubClient
    conn = get_db_connection()
    client = FinancialHubClient(conn)

    try:
        # 检测并创建数据表
        db.ensure_tables(conn)

        # 确定 crawl target
        if args.target_id:
            target = client.get_crawl_target_by_id(args.target_id)
            if not target:
                print(f"[ERROR] 未找到 target_id={args.target_id}", file=sys.stderr)
                sys.exit(1)
            targets = [target]
        else:
            targets = client.get_crawl_targets(source_type="sec_edgar", enabled=True)

        if not targets:
            print("[ERROR] 数据库中没有找到可用的 sec_edgar 抓取目标，终止运行", file=sys.stderr)
            sys.exit(1)

        for target in targets:
            print(f"\n[*] 处理目标: {target.target_name} (id={target.id})")

            # 自动识别 target_identifier 是 CIK（纯数字）还是 company 名称
            identifier = target.target_identifier or ""
            if identifier.isdigit():
                cik, company = identifier, ""
                print(f"    [识别] CIK={cik}")
            else:
                cik, company = "", identifier
                print(f"    [识别] Company={company}")

            # 通知开始
            run = client.notify_crawl_start(
                target_id=target.id,
                component_name=config.COMPONENT_NAME,
            )

            start_time = time.time()
            try:
                scraper = EdgarScraper(cik=cik, company=target.target_name, output_dir=args.file_path)
                entries, items_new = scraper.run(conn=conn)
                duration_ms = int((time.time() - start_time) * 1000)

                # 通知成功
                client.notify_crawl_end(
                    run_id=run.id,
                    target_id=target.id,
                    component_name=config.COMPONENT_NAME,
                    success=True,
                    items_found=len(entries),
                    items_new=items_new,
                    duration_ms=duration_ms,
                )
                print(f"\n[完成] 共获取 {len(entries)} 条，新增 {items_new} 条")

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)

                # 通知失败
                client.notify_crawl_end(
                    run_id=run.id,
                    target_id=target.id,
                    component_name=config.COMPONENT_NAME,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms,
                )
                print(f"\n[ERROR] 抓取失败: {e}", file=sys.stderr)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
