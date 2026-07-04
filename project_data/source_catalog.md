# 來源清單

這份清單先用來整理「股癌分析專區」要長期追的公開來源類型。  
原則是先列來源類別，不急著把所有 URL 寫死，避免日後更換連結或來源結構時要大改。

## 來源分類

| 來源類型 | 抓取方式 | 是否啟用 | 主要資料 | 備註 |
| --- | --- | --- | --- | --- |
| `youtube` | `auto_discovery` | 否 | 影片標題、描述、字幕/逐字稿 | 先由搜尋詞與 seed 頁面找影片，再進分析 |
| `podcast` | `auto_discovery` | 否 | RSS、單集頁、上架時間 | 先由 RSS/seed 發現單集連結 |
| `article` | `auto_discovery` | 否 | 文章全文、標題、段落 | 先由搜尋詞與 seed 頁面找可分析文章 |
| `social` | `auto_discovery` | 否 | 貼文內容、時間、回覆脈絡 | 先由 seed 或公開提及頁掃描候選貼文 |

## 建議優先順序

1. YouTube 影片與字幕
2. Podcast 節目頁與 RSS
3. 專訪與文章
4. 社群貼文

## 每種來源要抓的欄位

- `source_id`
- `source_type`
- `source_url`
- `published_at`
- `author`
- `title`
- `content`
- `raw_file`

## 後續執行策略

- 先建立自動發現規則
- 再把每個來源分類成固定解析器
- 最後才做跨來源論點合併
