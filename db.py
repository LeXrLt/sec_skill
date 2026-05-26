"""SEC EDGAR 爬虫数据库操作模块"""

import json
import os

import psycopg2


SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


def ensure_tables(conn):
    """检测并创建数据表（基于 schema.sql）。"""
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("[DB] 数据表检查/创建完成")


def get_existing_accnos(conn, target_id: int) -> set[str]:
    """查询指定 target 下已存在的 accession_no 集合，用于去重。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT accession_no FROM sec_edgar_filings WHERE target_id = %s",
            (target_id,),
        )
        return {row[0] for row in cur.fetchall()}


def insert_filing(conn, target_id: int, entry: dict, status: str = "ready") -> bool:
    """插入一条 filing 记录。如果 accession_no 已存在则跳过，返回是否新增。"""
    accno = entry.get("accession_no", "")
    if not accno:
        return False

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sec_edgar_filings
                (target_id, accession_no, filing_type, title, filed_at,
                 author, index_url, summary, local_paths, status, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (accession_no) DO UPDATE SET
                local_paths = EXCLUDED.local_paths,
                status = EXCLUDED.status,
                updated_at = NOW()
            RETURNING id
            """,
            (
                target_id,
                accno,
                entry.get("category", ""),
                entry.get("title", ""),
                entry.get("updated", ""),
                entry.get("author", ""),
                entry.get("link", ""),
                entry.get("summary", ""),
                json.dumps(entry.get("documents", {}), ensure_ascii=False),
                status,
                json.dumps(entry, ensure_ascii=False, default=str),
            ),
        )
    conn.commit()
    return True


def update_filing_status(conn, accession_no: str, status: str, local_paths: dict | None = None):
    """更新 filing 的状态和本地路径。"""
    if local_paths is not None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sec_edgar_filings
                SET status = %s, local_paths = %s, updated_at = NOW()
                WHERE accession_no = %s
                """,
                (status, json.dumps(local_paths, ensure_ascii=False), accession_no),
            )
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sec_edgar_filings
                SET status = %s, updated_at = NOW()
                WHERE accession_no = %s
                """,
                (status, accession_no),
            )
    conn.commit()
