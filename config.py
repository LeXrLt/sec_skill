"""SEC EDGAR 爬虫配置"""

import os
from dotenv import load_dotenv

load_dotenv()

# SEC EDGAR 页面 URL
EDGAR_PAGE_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"


# HTTP 请求头 — SEC 要求提供 User-Agent 并包含联系邮箱
HEADERS = {
    "User-Agent": "financial_web_fetch/1.0 (contact@example.com)",
    "Accept": "application/atom+xml, application/xml, text/xml, */*",
}

# 请求超时（秒）
REQUEST_TIMEOUT = 60

# 重试参数
MAX_RETRIES = 3           # 最大重试次数
RETRY_DELAY = 5           # 重试间隔（秒）

# 分页请求间隔（秒）— 避免触发 SEC 频率限制
PAGE_DELAY = 1

# 每下载 N 个文件后的延迟（秒）
DOWNLOAD_BATCH = 10       # 每批次文件数
DOWNLOAD_DELAY = 0.5      # 批次间延迟

# 输出目录
# 优先使用环境变量 CRAWLER_OUTPUT_DIR（由 financial_hub 在下载根目录后拼接 source_type 注入），
# 未设置时回退到项目内 output 目录。
OUTPUT_DIR = os.getenv("CRAWLER_OUTPUT_DIR", "output")

# PostgreSQL 数据库配置（financial_hub_postgres 插件，从 .env 读取）
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "financial_hub")

# 爬虫组件名称（用于 financial_hub_postgres 生命周期上报）
COMPONENT_NAME = "sec_edgar_crawler"
