-- SEC EDGAR 爬虫数据表
-- 用于记录每条抓取到的 filing，支持断点续传和去重

CREATE TABLE IF NOT EXISTS sec_edgar_filings (
    id              SERIAL PRIMARY KEY,
    accession_no    VARCHAR(30)     NOT NULL,
    company_name    VARCHAR(500)    NOT NULL DEFAULT '',
    cik             VARCHAR(20)     NOT NULL DEFAULT '',
    filing_type     VARCHAR(50)     NOT NULL DEFAULT '',
    title           VARCHAR(1000)   NOT NULL DEFAULT '',
    filed_at        VARCHAR(50)     DEFAULT NULL,
    index_url       VARCHAR(1000)   NOT NULL DEFAULT '',
    summary         TEXT            DEFAULT '',
    local_paths     JSONB           NOT NULL DEFAULT '{}',
    status          VARCHAR(50)     NOT NULL DEFAULT 'pending',
    raw_data        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sec_edgar_filings_accno UNIQUE (accession_no)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_sec_edgar_filings_cik
    ON sec_edgar_filings (cik);
CREATE INDEX IF NOT EXISTS idx_sec_edgar_filings_accno
    ON sec_edgar_filings (accession_no);
CREATE INDEX IF NOT EXISTS idx_sec_edgar_filings_status
    ON sec_edgar_filings (status);
CREATE INDEX IF NOT EXISTS idx_sec_edgar_filings_filed
    ON sec_edgar_filings (filed_at DESC);
