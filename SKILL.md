---
name: sec-edgar-crawl
description: Launch the SEC EDGAR crawler for a company the user names. Resolve the user's keyword (company name or stock ticker) to an official SEC CIK first, register/reuse a crawl target using that CIK, then run the crawler. Use whenever the user wants to fetch/scrape SEC filings for a specific company.
metadata:
  openclaw:
    emoji: "🕷️"
    requires:
      bins: ["python3"]
---

# SEC EDGAR 爬虫启动 Skill

本 skill 指引 agent 根据用户给出的**公司名或股票缩写**，主动启动 SEC EDGAR 爬虫，抓取该公司的提交文件（filings）。

## ⛔ 绝对禁止事项（最高优先级）

1. **严禁修改本 skill 中的任何源文件。** 包括但不限于 `main.py`、`scraper.py`、`config.py`、`db.py`、`schema.sql`、`requirements.txt`、`.env.example` 及任何 `.py` 文件。用户不具备改代码和 debug 的能力，任何代码改动都可能造成不可恢复的破坏。
2. 如果爬虫报错，**不要**通过改源码"修复"。只能：检查环境配置（见 `SKILL_SETUP.md`）、检查数据库连接、检查 CIK 是否正确、或如实把错误反馈给用户。
3. 允许的写操作仅限于：
   - 向 `crawl_targets` 数据表插入/查询抓取目标（数据操作，非代码）。
   - 通过命令行参数运行 `main.py`。
   - 读取 SEC 公开接口以解析 CIK。
4. 启动爬虫前，请始终向用户回显你将要抓取的 **公司名 + CIK**，避免抓错对象。

## When to use

当用户表达类似以下意图时使用本 skill：
- "帮我抓取 Apple 的 SEC filings"
- "爬一下特斯拉最近的提交"
- "Fetch SEC filings for NVDA"
- "看看微软在 SEC 上的最新文件"

用户给出的关键词可能是：**公司全名/简称**（如 `Apple`、`微软`）或 **股票代码**（如 `AAPL`、`TSLA`）。两者都**不能**直接当作爬虫目标——必须先解析为官方 **CIK**（Central Index Key）。

## 工作原理（为什么必须先查 CIK）

`main.py` 从数据库 `crawl_targets` 表读取抓取目标，并按 `target_identifier` 定位数据源：

- 若 `target_identifier` 是**纯数字** → 当作 **CIK**，爬虫据此构造正确的 RSS 地址（`scraper.py` 的 `?CIK=...`）。
- 若是**非数字**（公司名/股票代码）→ CIK 为空，RSS 地址无效，**抓不到正确数据**。

因此必须：**关键词 → CIK → 以 CIK 作为 `target_identifier` → 启动爬虫。**

## Step 0: 确认环境就绪

确认 `{baseDir}/.venv` 与 `{baseDir}/.env` 已存在。若未配置，先执行 `SKILL_SETUP.md` 完成环境初始化。**不要**在此步骤修改任何文件。

## Step 1: 将关键词解析为 CIK（主方法：官方 ticker/公司映射）

SEC 提供官方的 ticker→CIK→公司名映射文件。优先使用它解析，既能匹配股票代码也能匹配公司名（需提供 SEC 要求的 User-Agent）：

```bash
{baseDir}/.venv/bin/python -c "
import sys, requests
kw = sys.argv[1].strip()
ua = {'User-Agent': 'financial_web_fetch/1.0 (contact@example.com)'}
data = requests.get('https://www.sec.gov/files/company_tickers.json', headers=ua, timeout=60).json()
rows = list(data.values())
kwl = kw.lower()
exact = [r for r in rows if r['ticker'].lower() == kwl]
fuzzy = [r for r in rows if kwl in r['title'].lower() or kwl in r['ticker'].lower()]
hits = exact if exact else fuzzy
if not hits:
    print('NO_MATCH'); sys.exit(0)
for r in hits[:10]:
    print(f\"{str(r['cik_str']).zfill(10)}\t{r['ticker']}\t{r['title']}\")
" "用户的关键词"
```

输出格式为 `CIK<TAB>TICKER<TAB>公司名`，CIK 已补零为 10 位（如 `0000320193`）。

规则：
- **恰好一条**精确 ticker 匹配 → 直接使用该 CIK。
- **多条**模糊匹配 → 用 `ask_user_question` 让用户从候选公司中选择，确认后再继续。
- 输出 `NO_MATCH` → 进入 Step 1b 兜底。

## Step 1b: 兜底解析（无 ticker 的实体，如基金/个人/部分外国公司）

若 Step 1 无结果，使用 SEC 公司检索接口按名称查询（同样需要 User-Agent）：

```bash
{baseDir}/.venv/bin/python -c "
import sys, requests, re
from lxml import etree
kw = sys.argv[1].strip()
ua = {'User-Agent': 'financial_web_fetch/1.0 (contact@example.com)'}
url = ('https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany'
       f'&company={requests.utils.quote(kw)}&type=&dateb=&owner=include&count=10&output=atom')
xml = requests.get(url, headers=ua, timeout=60).content
ciks = sorted(set(re.findall(rb'<CIK>(\d+)</CIK>', xml)))
names = re.findall(rb'<conformed-name>(.*?)</conformed-name>', xml)
if not ciks:
    print('NO_MATCH'); sys.exit(0)
for c in ciks[:10]:
    print(c.decode().zfill(10))
" "用户的关键词"
```

若仍 `NO_MATCH`，向用户说明未能在 SEC 找到该公司，请其确认拼写或提供股票代码/CIK。**不要**猜测或编造 CIK。

## Step 2: 注册或复用抓取目标（写 crawl_targets 表，非改代码）

用解析得到的 CIK 创建抓取目标；若已存在同 CIK 的 `sec_edgar` 目标则复用，避免重复。使用读写数据库用户（`POSTGRES_USER`）：

```bash
{baseDir}/.venv/bin/python -c "
import os, sys, psycopg2
from dotenv import load_dotenv
load_dotenv('{baseDir}/.env')
cik, name = sys.argv[1], sys.argv[2]
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
    port=int(os.getenv('POSTGRES_PORT', '5432')),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'),
    dbname=os.getenv('POSTGRES_DB'),
)
cur = conn.cursor()
cur.execute(\"SELECT id FROM crawl_targets WHERE source_type='sec_edgar' AND target_identifier=%s\", (cik,))
row = cur.fetchone()
if row:
    print(f'EXISTING\t{row[0]}')
else:
    cur.execute(
        \"INSERT INTO crawl_targets (source_type, target_name, target_identifier, enabled) \"
        \"VALUES ('sec_edgar', %s, %s, true) RETURNING id\",
        (name, cik),
    )
    tid = cur.fetchone()[0]
    conn.commit()
    print(f'CREATED\t{tid}')
conn.close()
" "0000320193" "Apple Inc."
```

记下输出中的 `target_id`（`EXISTING` 或 `CREATED` 后面的数字），用于下一步。

## Step 3: 启动爬虫

用上一步的 `target_id` 运行爬虫主程序。**仅通过命令行参数运行，禁止改动 `main.py`。**

**默认行为：只下载最新的 100 条新提交。** 若这些已入库，会自动「往后顺延」抓取更早、尚未下载的提交，直到凑满 100 条或到达历史末尾。因此重复运行会逐步把更早的历史补齐，不会重复下载。

```bash
{baseDir}/.venv/bin/python {baseDir}/main.py --target-id <target_id>
```

按需调整数量与范围：

| 用户意图 | 命令 |
|---|---|
| 默认（最新 100 条新提交） | `... main.py --target-id <id>` |
| 指定数量（如最新 50 条） | `... main.py --target-id <id> -n 50` |
| **用户明确要求全量历史** | `... main.py --target-id <id> --all` |
| 指定下载目录 | 追加 `-f /目标/下载/目录`（默认输出到 `{baseDir}/output/`） |

**仅当用户明确要求「全部 / 全量 / all / 所有历史」时才使用 `--all`**，否则一律使用默认的 100 条限量模式，避免一次性抓取过多数据触发 SEC 频率限制。

## Step 4: 汇报结果

爬虫运行结束后向用户汇报：
- 抓取的公司名与 CIK。
- 本次「共获取 / 新增」的条数（见程序输出 `[完成]` 行）。
- 结果位置：JSON 汇总在 `{baseDir}/output/` 下，原始文档在 `{baseDir}/output/filings/<accession_no>/`；数据同时写入数据库 `sec_edgar_filings` 表。

## 完整示例

用户："帮我爬 AAPL 在 SEC 的提交"
1. Step 1 用 `AAPL` 解析 → `0000320193  AAPL  Apple Inc.`（精确匹配，直接采用）。
2. 向用户回显："将抓取 Apple Inc.（CIK 0000320193）"。
3. Step 2 注册/复用目标 → 得到 `target_id`。
4. Step 3 运行 `main.py --target-id <id>`。
5. Step 4 汇报抓取条数与输出路径。

用户："抓一下苹果公司的 filings"
1. Step 1 用 `苹果`/`Apple` 解析；若返回多条候选，用 `ask_user_question` 让用户确认是哪家公司。
2. 后续同上。

用户："爬一下某个没有股票代码的基金"
1. Step 1 返回 `NO_MATCH` → Step 1b 用公司名检索 CIK。
2. 确认后继续 Step 2~4。

用户："把特斯拉在 SEC 的全部历史提交都抓下来"
1. Step 1~2 解析 `TSLA` 的 CIK 并注册目标。
2. Step 3 因用户明确要求全量，使用 `--all` 运行。
3. Step 4 汇报。（未明确要求全量时，默认只下载最新 100 条。）

## 故障排查（不改源码）

| 现象 | 处理方式 |
|---|---|
| 数据库连不上 | 检查 `.env`（见 `SKILL_SETUP.md`），确认 PostgreSQL 可达、读写用户凭据正确 |
| `没有找到可用的 sec_edgar 抓取目标` | 说明 Step 2 未成功插入目标，重做 Step 2 并确认 `target_id` |
| 抓不到数据 / RSS 为空 | 确认 `target_identifier` 是**纯数字 CIK**；若是公司名说明 Step 1/2 出错，重新解析 CIK |
| 访问 SEC 超时 | SEC 有频率限制且需可访问 sec.gov；稍后重试或检查网络/代理 |
| 解析 CIK 报错缺少依赖 | 按 `SKILL_SETUP.md` 重新安装依赖，**不要**改源码 |

## 项目结构参考（只读，禁止修改其中源文件）

```
{baseDir}/
├── main.py             ← 爬虫入口（仅可用命令行参数运行，禁止修改）
├── scraper.py          ← 抓取逻辑（禁止修改）
├── config.py           ← 配置（禁止修改）
├── db.py               ← 数据库写入（禁止修改）
├── schema.sql          ← 表结构（禁止修改）
├── .env                ← 环境配置（凭据，不入库）
├── output/             ← 抓取结果输出目录
├── SKILL.md            ← 本文件（爬虫启动 skill）
└── SKILL_SETUP.md      ← 环境初始化 skill
```
