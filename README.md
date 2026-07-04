# Topic 22: 股癌分析專區

## 目標

這個專區用來蒐集、整理與分析「股癌」相關言論，將分散在不同來源的內容轉成可檢索、可追蹤、可歸納的論點資料。

專案核心不是單純存文字，而是把每一段言論整理成：
- 原始來源
- 發言時間
- 主題分類
- 論點摘要
- 支撐理由
- 可驗證的前提與風險

## 主要用途

- 爬搜股癌的公開言論
- 清洗與去重
- 將言論拆成可比較的論點單位
- 彙整成主題式分析報告
- 保留原文來源，方便回查與驗證

## 資料處理原則

- 先保留原始資料，再做摘要與分類
- 每一筆整理結果都要能回連到原始來源
- 只做公開資料整理，不處理未授權或私人內容
- 若同一論點在不同來源重複出現，需保留來源差異與時間差

## 建議資料結構

```text
projects/topic_22_stockguy_analysis
  project_data/
    raw/
    cleaned/
    notes/
  output/
    mentions.csv
    arguments.csv
    themes.csv
    reports/
  site/
  docs/
  scripts/
```

## 欄位建議

### 言論明細

- `source_id`
- `source_type`
- `source_url`
- `published_at`
- `author`
- `title`
- `content`
- `clean_content`
- `topic_tag`
- `argument_id`
- `confidence`

### 論點整理

- `argument_id`
- `theme`
- `argument_summary`
- `supporting_points`
- `assumptions`
- `risk_points`
- `related_sources`

## 後續建議

1. 先建立爬取來源清單
2. 再定義清洗與去重規則
3. 最後把論點整理成固定模板，方便持續更新

## 每日更新方式

- 直接執行 `daily_update.bat`
- 或用 Windows Task Scheduler 每天固定時間呼叫同一個 bat
- 每次跑完會同步產出 `docs/` 靜態站，適合直接上 GitHub Pages

## 來源設定

- `project_data/sources.json` 定義要抓的公開來源
- 每個來源可以設定 `enabled`、`url` 或 `urls`
- 來源抓取後會先寫入 `project_data/raw/*.jsonl`
- 再由規則式分析產出 `cleaned` 與 `output` 檔案
- 來源清單草案放在 `project_data/source_catalog.md`

## 靜態報告站

- 發佈入口：`docs/index.html`
- 前端會顯示最後更新時間、論點數、主題數
- 下拉選單可切換每日快照
- 搜尋框可直接篩論點與來源標題
- `sync_docs.bat` 預設會從 repo 根目錄執行 `git add / commit / push`
- 如果目前不在 git repo 內，先把整個 `D:\mainSD` 放進版本庫再用這個腳本

## 大盤與族群回測

- benchmark 預設由每日 pipeline 自動產生，不需要手動準備族群檔。
- 系統會先從每週股癌言論抽出候選族群，再用全市場公司資料與價格資料建立等權族群指數。
- 自動產出位置：`project_data/benchmarks/`
- 自動設計設定：`project_data/benchmark_design.json`
- 若要補外部 benchmark，可把 CSV 放在 `project_data/benchmark_sources/`，再執行 `python scripts/prepare_benchmarks.py`
