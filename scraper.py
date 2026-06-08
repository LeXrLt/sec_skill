"""SEC EDGAR RSS/Atom 订阅抓取器"""

import json
import os
import time
from datetime import datetime
from typing import Any

import feedparser
import requests
from lxml import html as lxml_html
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import config
import db

SEC_BASE_URL = "https://www.sec.gov"


class EdgarScraper:
    """SEC EDGAR 最新提交文件爬取器，基于 Atom RSS 订阅。"""

    def __init__(self, cik: str = "", company: str = "", output_dir: str | None = None):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self.cik = cik
        self.company = company
        self.rss_base = self._build_rss_base()
        self.page_url = config.EDGAR_PAGE_URL
        self.timeout = config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES
        self.retry_delay = config.RETRY_DELAY
        self.page_delay = config.PAGE_DELAY
        self.download_batch = config.DOWNLOAD_BATCH
        self.download_delay = config.DOWNLOAD_DELAY
        self.output_dir = output_dir if output_dir else config.OUTPUT_DIR

        os.makedirs(self.output_dir, exist_ok=True)

    def _build_rss_base(self) -> str:
        """根据 CIK 或 company 构建 RSS URL（不含分页参数，获取全部结果）。"""
        return (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?CIK={self.cik}"
            "&type="
            f"&company={self.company}"
            "&dateb="
            "&owner=include"
            "&output=atom"
        )

    # ------------------------------------------------------------------
    # 网络请求
    # ------------------------------------------------------------------

    def fetch_raw(self, url: str) -> str:
        """发起 GET 请求，带重试机制，返回响应文本。"""
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt < self.max_retries:
                    wait = self.retry_delay * attempt
                    print(f"[!] 请求失败 (第{attempt}次): {e}")
                    print(f"    等待 {wait} 秒后重试...")
                    time.sleep(wait)
                else:
                    raise

    def fetch_all_rss(self) -> list[dict[str, Any]]:
        """抓取 RSS 订阅的全部内容（不分页）。"""
        print(f"[*] 正在抓取 RSS: {self.rss_base}")
        xml_content = self.fetch_raw(self.rss_base)
        entries = self.parse_rss(xml_content)
        print(f"[+] 抓取完成，共 {len(entries)} 条")
        return entries

    def fetch_page(self) -> str:
        """抓取 EDGAR 页面的 HTML 内容。"""
        print(f"[*] 正在抓取页面: {self.page_url}")
        return self.fetch_raw(self.page_url)

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def parse_rss(self, xml_content: str) -> list[dict[str, Any]]:
        """解析 Atom XML，提取每条提交记录的关键字段。

        返回列表，每个元素为一条提交记录的字典，包含:
        - title: 标题
        - link: 链接
        - summary: 摘要
        - updated: 更新时间
        - category: 分类/表单类型
        - author: 提交者
        """
        feed = feedparser.parse(xml_content)

        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS 解析失败: {feed.bozo_exception}")

        entries: list[dict[str, Any]] = []
        for entry in feed.entries:
            record = {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "updated": entry.get("updated", ""),
                "category": self._extract_category(entry),
                "author": self._extract_author(entry),
            }
            entries.append(record)

        print(f"[+] 共解析到 {len(entries)} 条提交记录")
        return entries

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------

    def save_to_json(self, entries: list[dict[str, Any]], filename: str | None = None) -> str:
        """将解析结果保存为 JSON 文件，返回文件路径。"""
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"edgar_filings_{ts}.json"

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

        print(f"[+] 结果已保存至: {filepath}")
        return filepath

    def print_entries(self, entries: list[dict[str, Any]], limit: int = 10) -> None:
        """以易读格式打印前 N 条记录。"""
        show = entries[:limit]
        print(f"\n{'='*60}")
        print(f" SEC EDGAR 最新提交 (显示 {len(show)}/{len(entries)} 条)")
        print(f"{'='*60}")
        for i, e in enumerate(show, 1):
            print(f"\n--- [{i}] {e['title']}")
            print(f"    类型:   {e['category']}")
            print(f"    提交者: {e['author']}")
            print(f"    时间:   {e['updated']}")
            print(f"    链接:   {e['link']}")
            if e["summary"]:
                summary_preview = e["summary"][:120].replace("\n", " ")
                print(f"    摘要:   {summary_preview}...")

    # ------------------------------------------------------------------
    # 子页面解析与文件下载
    # ------------------------------------------------------------------

    @staticmethod
    def _accno_from_index_url(index_url: str) -> str:
        """从 index 页面 URL 中提取 AccNo 作为文件夹名。
        例: ...000119312526202063/0001193125-26-202063-index.htm
        返回: 0001193125-26-202063
        """
        basename = index_url.rsplit("/", 1)[-1]  # 0001193125-26-202063-index.htm
        return basename.replace("-index.htm", "").replace("-index.html", "")

    @staticmethod
    def _normalize_ix_url(url: str) -> str:
        """将 SEC 交互式查看器链接 ix?doc=/path 转换为直接文件链接。
        例: https://www.sec.gov/ix?doc=/Archives/edgar/data/.../xxx.htm
        返回: https://www.sec.gov/Archives/edgar/data/.../xxx.htm
        """
        if "/ix?doc=" in url:
            return url.replace("/ix?doc=", "")
        return url

    def extract_document_urls(self, index_url: str) -> list[dict[str, str]]:
        """访问 filing index 页面，从 'Document Format Files' 表格中
        提取所有文档行的信息（html / xml / txt）。

        返回列表，每个元素: {"description", "doc_name", "url", "type"}
        """
        try:
            page_html = self.fetch_raw(index_url)
        except Exception as e:
            print(f"[!] 无法访问索引页 {index_url}: {e}")
            return []

        tree = lxml_html.fromstring(page_html)

        tables = tree.xpath('//table[@summary="Document Format Files"]')
        if not tables:
            print(f"[!] 未找到 Document Format Files 表格: {index_url}")
            return []

        docs: list[dict[str, str]] = []
        table = tables[0]
        for row in table.xpath('.//tr'):
            cells = row.xpath('.//td')
            if len(cells) < 3:
                continue
            description = (cells[1].text_content() or "").strip()
            link_el = cells[2].xpath('.//a')
            if not link_el:
                continue
            href = link_el[0].get("href", "")
            doc_name = link_el[0].text_content().strip()
            doc_type = cells[3].text_content().strip() if len(cells) > 3 else ""
            raw_url = urljoin(SEC_BASE_URL, href)
            # 转换 ix?doc= 动态链接为直接文件链接
            normalized_url = self._normalize_ix_url(raw_url)
            docs.append({
                "description": description,
                "doc_name": doc_name,
                "url": normalized_url,
                "type": doc_type,
            })

        return docs

    def download_file(self, url: str, save_dir: str, filename: str | None = None) -> str | None:
        """下载文件到指定目录，返回相对于项目根目录的路径。"""
        os.makedirs(save_dir, exist_ok=True)

        if filename is None:
            filename = url.rsplit("/", 1)[-1]
        filepath = os.path.join(save_dir, filename)

        # 避免重复下载
        if os.path.exists(filepath):
            return filepath

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as e:
            print(f"[!] 下载失败 {url}: {e}")
            return None

        with open(filepath, "wb") as f:
            f.write(resp.content)

        return filepath

    def process_entries(
        self,
        entries: list[dict[str, Any]],
        conn=None,
        _depth: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """遍历每条记录，抓取 index 页面，下载 Document Format Files 表格中的
        所有文档（html / xml / txt），每个 AccNo 建立独立文件夹。
        如果提供了 conn，则跳过已入库的记录并将新记录写入数据库。
        _depth 用于限制递归深度，防止无限循环。"""
        MAX_DEPTH = 2
        if _depth >= MAX_DEPTH:
            print(f"[!] 达到最大递归深度 {MAX_DEPTH}，停止下钻")
            return entries, 0
        total = len(entries)
        downloaded_accnos: dict[str, dict[str, str]] = {}  # accno -> documents dict
        download_count = 0  # 累计下载计数，用于批次限速

        # 查询已入库的 accession_no，用于去重
        existing_accnos: set[str] = set()
        if conn:
            existing_accnos = db.get_existing_accnos(conn)
            if existing_accnos:
                print(f"[DB] 已有 {len(existing_accnos)} 条历史记录，将跳过重复项")

        items_new = 0
        items_skipped = 0
        all_sub_results: list[dict[str, Any]] = []

        for i, entry in enumerate(entries, 1):
            index_url = entry.get("link", "")

            # 非 filing 条目（如公司搜索结果页面），递归抓取下级 RSS
            if "-index.htm" not in index_url:
                sub_url = self._ensure_atom_output(index_url)
                print(f"[*] ({i}/{total}) 非 filing 条目，递归抓取下级: {sub_url}")
                try:
                    sub_xml = self.fetch_raw(sub_url)
                    sub_entries = self.parse_rss(sub_xml)
                    if sub_entries:
                        sub_results, sub_new = self.process_entries(
                            sub_entries, conn=conn, _depth=_depth + 1
                        )
                        all_sub_results.extend(sub_results)
                        items_new += sub_new
                except Exception as e:
                    print(f"    [!] 下级抓取失败: {e}")
                entry["accession_no"] = ""
                entry["documents"] = {}
                continue

            accno = self._accno_from_index_url(index_url)
            entry["accession_no"] = accno
            print(f"[*] ({i}/{total}) 处理: {entry['title'][:50]}...")

            # 数据库中已存在，跳过
            if accno in existing_accnos:
                entry["documents"] = {}
                items_skipped += 1
                print(f"    [✓] 已入库，跳过: {accno}")
                continue

            # 同一批次中同一个 AccNo 已处理过，直接复用结果
            if accno in downloaded_accnos:
                entry["documents"] = downloaded_accnos[accno]
                print(f"    [=] 复用已下载: {accno}")
                continue

            docs = self.extract_document_urls(index_url)
            if not docs:
                entry["documents"] = {}
                downloaded_accnos[accno] = {}
                # 记录到数据库（状态 failed）
                if conn:
                    try:
                        db.insert_filing(conn, entry, company_name=self.company, cik=self.cik, status="failed")
                    except Exception as db_err:
                        conn.rollback()
                        print(f"    [!] 入库失败: {db_err}")
                continue

            filing_dir = os.path.join(self.output_dir, "filings", accno)
            documents: dict[str, str] = {}

            for doc in docs:
                doc_name = doc["doc_name"]
                # 优先使用 SEC 表格中的 Type 字段作为 key（如 10-Q、EX-32.2）
                doc_type = doc.get("type", "").strip()
                if doc_type:
                    key = doc_type
                elif doc_name.endswith(".html") or doc_name.endswith(".htm"):
                    key = "html"
                elif doc_name.endswith(".xml"):
                    key = "xml"
                elif doc_name.endswith(".txt"):
                    key = "txt"
                else:
                    key = doc_name  # 其他类型保留原名

                local_path = self.download_file(doc["url"], filing_dir, doc_name)
                if local_path:
                    documents[key] = local_path
                    print(f"    [+] {key}: {local_path}")
                    download_count += 1
                    if download_count % self.download_batch == 0:
                        time.sleep(self.download_delay)

            entry["documents"] = documents
            downloaded_accnos[accno] = documents

            # 写入数据库
            if conn:
                try:
                    db.insert_filing(conn, entry, company_name=self.company, cik=self.cik, status="ready")
                    items_new += 1
                except Exception as db_err:
                    conn.rollback()
                    print(f"    [!] 入库失败: {db_err}")

        # 合并子结果
        entries.extend(all_sub_results)
        print(f"[+] 处理完成: 新增 {items_new} 条，跳过 {items_skipped} 条")
        return entries, items_new

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_atom_output(url: str) -> str:
        """确保 URL 包含 output=atom 参数，若不存在则添加。"""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "output" not in params:
            separator = "&" if parsed.query else "?"
            return f"{url}{separator}output=atom"
        return url

    @staticmethod
    def _extract_category(entry) -> str:
        """从 Atom entry 中提取 category/表单类型。"""
        tags = entry.get("tags", [])
        if tags:
            return tags[0].get("term", "")
        return entry.get("category", "")

    @staticmethod
    def _extract_author(entry) -> str:
        """从 Atom entry 中提取 author 名称。"""
        author_detail = entry.get("author_detail", {})
        if author_detail:
            return author_detail.get("name", "")
        return entry.get("author", "")

    # ------------------------------------------------------------------
    # 高层接口
    # ------------------------------------------------------------------

    def run(self, conn=None) -> tuple[list[dict[str, Any]], int]:
        """执行完整抓取流程: 抓取 → 下载 → 入库 → 保存 → 打印。
        返回 (entries, items_new)。"""
        entries = self.fetch_all_rss()
        items_new = 0

        if entries:
            entries, items_new = self.process_entries(entries, conn=conn)
            self.save_to_json(entries)
            self.print_entries(entries)
        else:
            print("[!] 未获取到任何提交记录")

        return entries, items_new
