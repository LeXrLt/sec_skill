# SEC EDGAR Filings Fetcher

从美国证券交易委员会（SEC）EDGAR 数据库自动抓取最新文件提交记录。

> **你不需要懂任何编程或命令行知识。** 只要在 OpenClaw 对话框中用自然语言说出需求，OpenClaw 会帮你完成一切。

---

## 安装

在 OpenClaw 对话框中说：

> "帮我安装 SEC EDGAR 抓取工具，https://github.com/LeXrLt/sec_skill.git"

OpenClaw 会自动完成以下操作：
1. 下载代码
2. 配置运行环境
3. 安装所需依赖

整个过程无需你手动输入任何命令。

---

## 使用

安装完成后，直接用自然语言告诉 OpenClaw 你想做什么即可。例如：

| 你想做的事 | 对 OpenClaw 说 |
|---|---|
| 抓取最新 100 条提交 | "查一下 SEC 上最近的 100 条记录" |
| 抓取最新 50 条提交 | "帮我拉取 SEC 最新的 50 条 filing" |
| 看看最近有什么提交 | "看看 SEC 最近有什么提交" |
| 英文也行 | "Fetch the latest 50 SEC filings" |

不需要记住数量、参数或格式——用你习惯的方式描述需求就好。

---

## 输出结果

运行结束后，OpenClaw 会告诉你结果保存在哪里。默认输出在 `output/` 文件夹中：

- **JSON 文件** — 包含每条提交的标题、作者、时间、分类、摘要等结构化信息
- **原始文件** — 每条提交对应的 HTML / XML 原文档

你可以直接让 OpenClaw 帮你打开或解读这些文件。

---

## 常见问题

**Q: 需要翻墙吗？**
A: 需要能访问 SEC 官网（sec.gov）。如果网络受限，请确保代理可用。

**Q: 抓取速度很慢？**
A: SEC 对请求频率有限制，工具已内置合理的延迟策略，耐心等待即可。

**Q: 想修改抓取配置怎么办？**
A: 告诉 OpenClaw，比如"把每批下载数量改成 20"，它会帮你修改。

---

## 触发关键词

以下说法均可触发此技能：

- "查一下 SEC 上最近的 100 条记录"
- "Fetch the latest 50 SEC filings"
- "帮我爬取 SEC EDGAR 最新的 200 条提交"
- "看看 SEC 最近有什么提交"

---

## 数据库结构

抓取的数据存储在 PostgreSQL 数据库的 `sec_edgar_filings` 表中：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL | 数据库自增主键 |
| `accession_no` | VARCHAR(30) | SEC 提交唯一编号（如 `0001047469-16-010081`） |
| `company_name` | VARCHAR(500) | 公司名称 |
| `cik` | VARCHAR(20) | 公司 CIK 编号（Central Index Key） |
| `filing_type` | VARCHAR(50) | 表单类型（如 `10-K`、`10-Q`、`8-K`、`4` 等） |
| `title` | VARCHAR(1000) | 提交标题 |
| `filed_at` | VARCHAR(50) | 提交时间（ISO 8601 格式） |
| `index_url` | VARCHAR(1000) | SEC 官方索引页面链接 |
| `summary` | TEXT | 提交摘要描述 |
| `local_paths` | JSONB | 下载文件的本地绝对路径，键为 Type 字段（如 `{"10-Q": "/path/a.htm", "EX-32.2": "/path/b.htm"}`） |
| `status` | VARCHAR(50) | 处理状态：`ready`（成功）、`failed`（失败）、`pending`（待处理） |
| `raw_data` | JSONB | 原始抓取数据的完整备份 |
| `created_at` | TIMESTAMPTZ | 数据库记录创建时间 |
| `updated_at` | TIMESTAMPTZ | 数据库记录更新时间 |

### 字段说明

- **`filing_type`**：来自 SEC RSS feed 的表单类型代码，常见值包括：
  - `10-K` — 年度报告
  - `10-Q` — 季度报告
  - `8-K` — 重大事件报告
  - `4` — 内部交易报告
  - `S-1` — 招股说明书

- **`local_paths`**：存储下载到本地的所有文档路径，使用 SEC index 页面中 `Type` 列的值作为键（如 `10-Q`、`EX-31.1`、`EX-32.2`），方便区分财报正文与各类附件。值为绝对路径。
