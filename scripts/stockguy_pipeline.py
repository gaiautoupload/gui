from __future__ import annotations

import csv
import json
import re
import hashlib
import urllib.request
from urllib.parse import quote_plus
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Mention:
    source_id: str
    source_type: str
    source_url: str
    published_at: str
    author: str
    title: str
    content: str
    clean_content: str
    topic_tag: str
    argument_id: str
    confidence: str


@dataclass
class RawMention:
    source_id: str
    source_type: str
    source_url: str
    published_at: str
    author: str
    title: str
    content: str

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "published_at": self.published_at,
            "author": self.author,
            "title": self.title,
            "content": self.content,
        }


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?；;\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def parse_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def week_start(dt: datetime) -> str:
    start = dt - timedelta(days=dt.weekday())
    return start.strftime("%Y-%m-%d")


def classify_theme(text: str, theme_map: dict[str, list[str]]) -> str:
    hits = []
    for theme, keywords in theme_map.items():
        score = sum(1 for kw in keywords if kw in text)
        if score:
            hits.append((score, theme))
    if not hits:
        return "other"
    hits.sort(key=lambda x: (-x[0], x[1]))
    return hits[0][1]


def classify_direction(text: str) -> str:
    up_words = ["看多", "看漲", "上漲", "反彈", "利多", "偏多", "多頭", "做多", "買進", "bull", "long"]
    down_words = ["看空", "看跌", "下跌", "回檔", "利空", "偏空", "空頭", "賣出", "避開", "bear", "short"]
    up = sum(text.count(w) for w in up_words)
    down = sum(text.count(w) for w in down_words)
    if up > down:
        return "bullish"
    if down > up:
        return "bearish"
    return "neutral"


def classify_scope(text: str, sector_map: dict) -> str:
    if any(kw in text for kw in ["大盤", "加權", "台股", "指數", "盤勢", "市場"]):
        return "market"
    return "theme"


def build_argument_id(theme: str, text: str) -> str:
    key = normalize_text(text)[:120]
    digest = hashlib.sha1(f"{theme}|{key}".encode("utf-8")).hexdigest()[:10]
    return f"{theme}-{digest}"


def dedupe_mentions(mentions: Iterable[Mention]) -> list[Mention]:
    seen = set()
    deduped = []
    for m in mentions:
        key = (m.source_url, m.clean_content)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    return deduped


def mention_date(mention: Mention) -> datetime | None:
    dt = parse_date(mention.published_at)
    if dt:
        return dt
    raw = re.match(r"(\d{8})_", mention.source_id)
    if raw:
        try:
            return datetime.strptime(raw.group(1), "%Y%m%d")
        except ValueError:
            return None
    return None


def load_raw_mentions(input_dir: Path) -> list[dict]:
    items = []
    for path in sorted(input_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                obj["_raw_file"] = str(path.name)
                items.append(obj)
    return items


def save_raw_mentions(input_dir: Path, rows: list[RawMention], source_name: str) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    path = input_dir / f"{stamp}_{source_name}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    return path


def fetch_url(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
    for encoding in ("utf-8", "utf-8-sig", "cp950", "big5"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def discover_urls(source: dict) -> list[str]:
    urls = []
    for url in source.get("seed_urls", []) or []:
        if url:
            urls.append(url)
    for query in source.get("search_queries", []) or []:
        if not query:
            continue
        search_url = f"https://www.google.com/search?q={quote_plus(query)}"
        urls.append(search_url)
    return list(dict.fromkeys(urls))


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_meta(html: str, name: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            return strip_html(match.group(1))
    return ""


def extract_article_text(html: str) -> str:
    candidates = []
    for pattern in [
        r"(?is)<article[^>]*>(.*?)</article>",
        r"(?is)<main[^>]*>(.*?)</main>",
        r"(?is)<div[^>]+class=['\"][^'\"]*(content|article|post|entry)[^'\"]*['\"][^>]*>(.*?)</div>",
    ]:
        for match in re.finditer(pattern, html):
            candidates.append(strip_html(match.group(match.lastindex or 1)))
    if candidates:
        return max(candidates, key=len)
    return strip_html(html)


def load_benchmark_series(path: Path) -> list[tuple[datetime, float]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_date(row.get("trade_date", ""))
            close = row.get("close", "")
            try:
                price = float(str(close).replace(",", ""))
            except ValueError:
                continue
            if dt:
                rows.append((dt, price))
    rows.sort(key=lambda x: x[0])
    return rows


def price_change_direction(series: list[tuple[datetime, float]], start_dt: datetime, horizon_days: int = 5) -> str | None:
    if not series:
        return None
    target_dt = start_dt + timedelta(days=horizon_days)
    start_price = None
    end_price = None
    for dt, price in series:
        if dt <= start_dt:
            start_price = price
        if dt <= target_dt:
            end_price = price
    if start_price is None or end_price is None:
        return None
    return "up" if end_price > start_price else "down" if end_price < start_price else "flat"


def slugify_benchmark_name(value: str) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text or "unknown"


def load_company_universe(company_master_path: Path) -> list[dict]:
    if not company_master_path.exists():
        return []
    with company_master_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def group_keywords(group: str, benchmark_design: dict) -> list[str]:
    aliases = benchmark_design.get("aliases", {})
    keys = [group]
    lower_group = group.lower()
    for alias, words in aliases.items():
        if alias.lower() == lower_group or alias in group or group in alias:
            keys.extend(words)
    return [k for k in dict.fromkeys(keys) if k]


def select_group_members(group: str, companies: list[dict], benchmark_design: dict) -> list[str]:
    keywords = group_keywords(group, benchmark_design)
    scored = []
    for row in companies:
        stock_id = str(row.get("stock_id", "")).strip()
        haystack = " ".join(
            str(row.get(field, ""))
            for field in ("company_name", "industry", "market", "security_type")
        )
        score = sum(1 for kw in keywords if kw and kw in haystack)
        if score and stock_id:
            scored.append((score, stock_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    max_members = int(benchmark_design.get("max_members", 30))
    return [stock_id for _, stock_id in scored[:max_members]]


def load_close_map(path: Path) -> dict[str, float]:
    closes = {}
    if not path.exists():
        return closes
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = str(row.get("trade_date", "")).strip()
            close_text = str(row.get("close", "")).replace(",", "").strip()
            if not date or not close_text:
                continue
            try:
                close = float(close_text)
            except ValueError:
                continue
            closes[date] = close
    return closes


def build_equal_weight_index(stock_ids: list[str], price_dir: Path) -> list[dict]:
    normalized_by_stock = []
    for stock_id in stock_ids:
        closes = load_close_map(price_dir / f"{stock_id}.csv")
        if not closes:
            continue
        first_date = min(closes)
        base = closes[first_date]
        if not base:
            continue
        normalized_by_stock.append({date: close / base * 100.0 for date, close in closes.items()})
    if not normalized_by_stock:
        return []
    all_dates = sorted({date for series in normalized_by_stock for date in series})
    rows = []
    for date in all_dates:
        values = [series[date] for series in normalized_by_stock if date in series]
        if not values:
            continue
        close = sum(values) / len(values)
        rows.append({"trade_date": date, "open": close, "high": close, "low": close, "close": close, "volume": len(values)})
    return rows


def write_benchmark(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["trade_date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)


def design_dynamic_benchmarks(
    weekly_analysis: list[dict],
    benchmark_dir: Path,
    company_master_path: Path,
    price_dir: Path,
    benchmark_design: dict,
) -> dict:
    companies = load_company_universe(company_master_path)
    manifest = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), "groups": []}
    if not companies or not price_dir.exists():
        save_json(benchmark_dir / "_manifest.json", manifest)
        return manifest

    market_name = benchmark_design.get("market_benchmark_name", "twii")
    all_stock_ids = [str(row.get("stock_id", "")).strip() for row in companies if str(row.get("stock_id", "")).strip()]
    market_rows = build_equal_weight_index(all_stock_ids[: int(benchmark_design.get("market_member_limit", 5000))], price_dir)
    if market_rows:
        write_benchmark(benchmark_dir / f"{market_name}.csv", market_rows)
        manifest["groups"].append({"group": "market", "benchmark": market_name, "members": len(all_stock_ids), "rows": len(market_rows)})

    min_members = int(benchmark_design.get("min_members", 3))
    groups = []
    for week in weekly_analysis:
        groups.extend(week.get("candidate_groups", []))
    for group in dict.fromkeys(groups):
        members = select_group_members(group, companies, benchmark_design)
        if len(members) < min_members:
            manifest["groups"].append({"group": group, "benchmark": slugify_benchmark_name(group), "members": len(members), "rows": 0, "status": "too_few_members"})
            continue
        bench_name = slugify_benchmark_name(group)
        rows = build_equal_weight_index(members, price_dir)
        if rows:
            write_benchmark(benchmark_dir / f"{bench_name}.csv", rows)
        manifest["groups"].append({"group": group, "benchmark": bench_name, "members": len(members), "rows": len(rows), "status": "written" if rows else "no_price_rows"})
    save_json(benchmark_dir / "_manifest.json", manifest)
    return manifest


def collect_from_source(source: dict) -> list[RawMention]:
    urls = source.get("urls", []) or ([source["url"]] if source.get("url") else [])
    if not urls:
        urls = discover_urls(source)
    source_type = str(source.get("type", "web"))
    source_name = str(source.get("name", "source"))
    author = str(source.get("author", "股癌"))
    items: list[RawMention] = []
    for idx, url in enumerate(urls, start=1):
        if "google.com/search" in url:
            html = fetch_url(url)
            for found in re.findall(r'/url\?q=(https?://[^&"]+)', html):
                urls.append(found)
            continue
        html = fetch_url(url)
        title = (
            extract_meta(html, "og:title")
            or extract_meta(html, "twitter:title")
            or strip_html(re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S).group(1))
            if re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
            else source_name
        )
        description = extract_meta(html, "og:description") or extract_meta(html, "description")
        article = extract_article_text(html)
        content = normalize_text(" ".join(part for part in [title, description, article] if part))
        items.append(
            RawMention(
                source_id=f"{source_name}-{idx:03d}",
                source_type=source_type,
                source_url=url,
                published_at=str(source.get("published_at", "")),
                author=author,
                title=title[:200],
                content=content,
            )
        )
    return items


def coerce_mention(obj: dict, theme_map: dict[str, list[str]]) -> Mention:
    content = normalize_text(obj.get("content", ""))
    topic_tag = classify_theme(content, theme_map)
    return Mention(
        source_id=str(obj.get("source_id", "")),
        source_type=str(obj.get("source_type", "unknown")),
        source_url=str(obj.get("source_url", "")),
        published_at=str(obj.get("published_at", "")),
        author=str(obj.get("author", "股癌")),
        title=str(obj.get("title", "")),
        content=content,
        clean_content=content,
        topic_tag=topic_tag,
        argument_id=build_argument_id(topic_tag, content),
        confidence=str(obj.get("confidence", "rule")),
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_report(mentions: list[Mention]) -> str:
    theme_counter = Counter(m.topic_tag for m in mentions)
    arg_groups = defaultdict(list)
    for m in mentions:
        arg_groups[m.argument_id].append(m)

    lines = []
    lines.append("# Daily Stockguy Report")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}")
    lines.append(f"- Mentions: {len(mentions)}")
    lines.append(f"- Themes: {len(theme_counter)}")
    lines.append("")
    lines.append("## Theme Counts")
    for theme, count in theme_counter.most_common():
        lines.append(f"- {theme}: {count}")
    lines.append("")
    lines.append("## Argument Briefs")
    for argument_id, group in sorted(arg_groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:20]:
        sample = group[0]
        sentences = []
        for item in group:
            sentences.extend(split_sentences(item.clean_content))
        freq = Counter(sentences)
        supporting = [s for s, _ in freq.most_common(3)]
        sources = [m.source_url for m in group if m.source_url]
        lines.append(f"### {argument_id} [{sample.topic_tag}] x{len(group)}")
        lines.append(f"- 核心論點: {sample.clean_content[:180]}")
        if supporting:
            lines.append(f"- 常見表述: {' / '.join(supporting)}")
        if sources:
            lines.append(f"- 來源數: {len(set(sources))}")
        lines.append("")
    return "\n".join(lines) + "\n"


def extract_phrase_candidates(items: list[Mention], theme_map: dict[str, list[str]]) -> list[str]:
    phrases = []
    for item in items:
        for theme, keywords in theme_map.items():
            if any(kw in item.clean_content for kw in keywords):
                phrases.append(theme)
    if phrases:
        return [theme for theme, _ in Counter(phrases).most_common(3)]
    tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", " ".join(m.clean_content for m in items))
    stop = {"股癌", "大盤", "台股", "市場", "今天", "最近", "因為", "這個", "那個"}
    token_counts = Counter(t for t in tokens if t not in stop)
    return [token for token, _ in token_counts.most_common(3)]


def build_weekly_analysis(mentions: list[Mention], theme_map: dict[str, list[str]]) -> list[dict]:
    weekly = defaultdict(list)
    for m in mentions:
        dt = mention_date(m)
        if not dt:
            continue
        weekly[week_start(dt)].append(m)

    weeks = []
    for wk, items in sorted(weekly.items()):
        text_blob = " ".join(m.clean_content for m in items)
        direction = classify_direction(text_blob)
        scope_counter = Counter(classify_scope(m.clean_content, {}) for m in items)
        theme_counter = Counter(m.topic_tag for m in items)
        core_theme = theme_counter.most_common(1)[0][0] if theme_counter else "other"
        top_scope = "market" if scope_counter.get("market") else "theme"
        candidate_groups = extract_phrase_candidates(items, theme_map)
        weeks.append(
            {
                "week_start": wk,
                "mention_count": len(items),
                "direction": direction,
                "scope": top_scope,
                "core_theme": core_theme,
                "candidate_groups": candidate_groups,
                "top_themes": [{"theme": k, "count": v} for k, v in theme_counter.most_common(5)],
                "highlights": [m.clean_content[:120] for m in items[:5]],
            }
        )
    return weeks


def find_benchmark_files(benchmark_dir: Path) -> dict[str, Path]:
    return {p.stem: p for p in benchmark_dir.glob("*.csv") if p.is_file()}


def build_accuracy_report(weekly_analysis: list[dict], benchmark_dir: Path) -> dict:
    files = find_benchmark_files(benchmark_dir)
    accuracy_rows = []
    for week in weekly_analysis:
        week_dt = parse_date(week["week_start"])
        if not week_dt:
            continue
        targets = []
        if week["scope"] == "market":
            targets.append("twii")
        for group in week.get("candidate_groups", []):
            targets.append(slugify_benchmark_name(group))
        for bench_key in dict.fromkeys(targets):
            bench_file = files.get(bench_key)
            if not bench_file:
                continue
            series = load_benchmark_series(bench_file)
            if not series:
                continue
            observed = price_change_direction(series, week_dt)
            if observed is None:
                continue
            predicted = week["direction"]
            hit = (
                (predicted == "bullish" and observed == "up")
                or (predicted == "bearish" and observed == "down")
                or (predicted == "neutral" and observed == "flat")
            )
            accuracy_rows.append(
                {
                    "week_start": week["week_start"],
                    "scope": week["scope"],
                    "group": bench_key,
                    "predicted": predicted,
                    "observed": observed,
                    "hit": hit,
                }
            )

    hits = sum(1 for r in accuracy_rows if r["hit"])
    total = len(accuracy_rows)
    return {
        "total_weeks": total,
        "hits": hits,
        "accuracy": round(hits / total, 4) if total else None,
        "rows": accuracy_rows,
    }


def write_weekly_report(weekly_analysis: list[dict], accuracy_report: dict, path: Path) -> None:
    lines = []
    lines.append("# Weekly Stockguy Report")
    lines.append("")
    lines.append(f"- Weeks analyzed: {len(weekly_analysis)}")
    lines.append(f"- Accuracy samples: {accuracy_report['total_weeks']}")
    if accuracy_report["accuracy"] is not None:
        lines.append(f"- Direction accuracy: {accuracy_report['accuracy']:.2%}")
    lines.append("")
    lines.append("## Weekly Focus")
    for week in weekly_analysis[-12:]:
        lines.append(f"### {week['week_start']}")
        lines.append(f"- Scope: {week['scope']}")
        lines.append(f"- Direction: {week['direction']}")
        lines.append(f"- Core theme: {week['core_theme']}")
        if week.get("candidate_groups"):
            lines.append(f"- Candidate groups: {' / '.join(week['candidate_groups'])}")
        lines.append(f"- Mentions: {week['mention_count']}")
        if week["highlights"]:
            lines.append(f"- Highlights: {' / '.join(week['highlights'][:3])}")
        lines.append("")
    lines.append("## Accuracy")
    if accuracy_report["rows"]:
        for row in accuracy_report["rows"][-20:]:
            lines.append(f"- {row['week_start']} [{row['group']}] predicted={row['predicted']} observed={row['observed']} hit={row['hit']}")
    else:
        lines.append("- No benchmark data available")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_site_payload(mentions: list[Mention]) -> dict:
    theme_counter = Counter(m.topic_tag for m in mentions)
    arg_groups = defaultdict(list)
    for m in mentions:
        arg_groups[m.argument_id].append(m)

    reports = []
    for argument_id, group in sorted(arg_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        sample = group[0]
        sentences = []
        for item in group:
            sentences.extend(split_sentences(item.clean_content))
        freq = Counter(sentences)
        reports.append(
            {
                "argument_id": argument_id,
                "theme": sample.topic_tag,
                "count": len(group),
                "core": sample.clean_content[:180],
                "supporting_points": [s for s, _ in freq.most_common(3)],
                "sources": [{"title": m.title, "url": m.source_url, "published_at": m.published_at} for m in group],
            }
        )

    return {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mention_count": len(mentions),
        "theme_count": len(theme_counter),
        "theme_counts": dict(theme_counter.most_common()),
        "reports": reports,
    }


def write_site_files(site_data: dict, docs_dir: Path) -> None:
    data_dir = docs_dir / "data"
    daily_dir = data_dir / "daily"
    report_dir = data_dir / "reports"
    ensure_dir(daily_dir)
    ensure_dir(report_dir)

    report_date = site_data.get("report_date", datetime.now().strftime("%Y-%m-%d"))
    save_json(daily_dir / f"{report_date}.json", site_data)

    snapshots = []
    for path in sorted(daily_dir.glob("*.json"), reverse=True):
        snap = load_json(path, {})
        snapshots.append(
            {
                "report_date": snap.get("report_date", path.stem),
                "generated_at": snap.get("generated_at", ""),
                "mention_count": snap.get("mention_count", 0),
                "theme_count": snap.get("theme_count", 0),
            }
        )

    save_json(data_dir / "index.json", {"latest": site_data, "snapshots": snapshots})
    for report in site_data.get("reports", []):
        save_json(report_dir / f"{report['argument_id']}.json", report)

    index_html = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="股癌分析專區，依日期查看每日論點整理與更新紀錄。" />
  <title>股癌分析專區</title>
  <link rel="stylesheet" href="./assets/site.css" />
</head>
<body>
  <div class="page-shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Topic 22 / Stockguy Analysis</p>
        <h1>股癌分析專區</h1>
        <p class="lead">每日自動抓取、整理與歸納公開言論，按日期切換報告，保留來源可追溯。</p>
      </div>
      <div class="hero-metrics">
        <div class="metric"><span class="metric-label">最後更新</span><strong id="generatedAt">-</strong></div>
        <div class="metric"><span class="metric-label">論點數</span><strong id="argumentCount">-</strong></div>
        <div class="metric"><span class="metric-label">主題數</span><strong id="themeCount">-</strong></div>
      </div>
    </header>
    <main class="layout">
      <section class="panel controls">
        <div class="control-row">
          <label for="reportDate">選擇日期</label>
          <select id="reportDate"></select>
        </div>
        <div class="control-row">
          <label for="searchBox">搜尋論點</label>
          <input id="searchBox" type="search" placeholder="輸入關鍵字，例如 AI、風控、半導體" />
        </div>
      </section>
      <section class="panel summary">
        <div class="section-head">
          <h2>日期報告</h2>
          <span id="reportMeta" class="meta-pill"></span>
        </div>
        <article id="dailySummary" class="summary-card"></article>
        <p class="muted" style="margin-top:12px;">週分析與一年準確度報告會同步輸出到 `output/weekly_report.md`。</p>
      </section>
      <section class="panel">
        <div class="section-head">
          <h2>論點卡片</h2>
          <span class="meta-pill">可點來源追回原文</span>
        </div>
        <div id="reportList" class="cards"></div>
      </section>
    </main>
  </div>
  <script src="./assets/site.js"></script>
</body>
</html>
"""

    site_css = """
:root {
  color-scheme: dark;
  --bg: #0b1020;
  --panel: rgba(13, 18, 35, 0.82);
  --panel-border: rgba(173, 193, 255, 0.12);
  --text: #e8ecff;
  --muted: #97a2c6;
  --accent: #8dd6ff;
  --accent-2: #ffd166;
  --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(141, 214, 255, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(255, 209, 102, 0.12), transparent 25%),
    linear-gradient(180deg, #0b1020 0%, #0d1328 100%);
  color: var(--text);
}
.page-shell { max-width: 1280px; margin: 0 auto; padding: 32px 20px 48px; }
.hero { display: grid; gap: 24px; grid-template-columns: 1.6fr 1fr; align-items: end; margin-bottom: 24px; }
.eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .18em; font-size: 12px; }
h1 { font-size: clamp(2.8rem, 6vw, 5rem); margin: 0 0 8px; line-height: .95; }
.lead { max-width: 62ch; color: var(--muted); font-size: 1.05rem; }
.hero-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.metric, .panel, .summary-card {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  box-shadow: var(--shadow);
  backdrop-filter: blur(18px);
  border-radius: 20px;
}
.metric { padding: 16px; }
.metric-label, .meta-pill, label { color: var(--muted); font-size: 12px; }
.metric strong { display: block; font-size: 1.6rem; margin-top: 6px; }
.layout { display: grid; gap: 18px; }
.panel { padding: 18px; }
.controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.control-row { display: grid; gap: 8px; }
select, input {
  width: 100%; padding: 14px 15px; border-radius: 14px;
  background: rgba(255,255,255,.04); color: var(--text);
  border: 1px solid rgba(255,255,255,.12); outline: none;
}
.section-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.meta-pill { padding: 8px 12px; border-radius: 999px; background: rgba(141, 214, 255, 0.08); }
.summary-card { padding: 18px; min-height: 120px; }
.cards { display: grid; gap: 14px; }
.card { padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02)); border: 1px solid rgba(255,255,255,.08); }
.card h3 { margin: 0 0 8px; font-size: 1.1rem; }
.card .tag { color: var(--accent-2); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
.sources { margin-top: 14px; display: grid; gap: 8px; }
.sources a { color: var(--accent); text-decoration: none; }
.muted { color: var(--muted); }
@media (max-width: 900px) { .hero, .controls, .hero-metrics { grid-template-columns: 1fr; } }
"""

    site_js = """
const state = { data: null, selectedDate: null, query: "" };
const els = {
  generatedAt: document.getElementById('generatedAt'),
  argumentCount: document.getElementById('argumentCount'),
  themeCount: document.getElementById('themeCount'),
  reportDate: document.getElementById('reportDate'),
  searchBox: document.getElementById('searchBox'),
  reportMeta: document.getElementById('reportMeta'),
  dailySummary: document.getElementById('dailySummary'),
  reportList: document.getElementById('reportList')
};
async function loadData() {
  const resp = await fetch('./data/index.json', { cache: 'no-store' });
  state.data = await resp.json();
  renderDateOptions();
  await loadSelectedReport();
}
function renderDateOptions() {
  els.reportDate.innerHTML = '';
  const snapshots = state.data.snapshots || [];
  (snapshots.length ? snapshots : [state.data.latest]).forEach(item => {
    const option = document.createElement('option');
    option.value = item.report_date;
    option.textContent = item.report_date;
    els.reportDate.appendChild(option);
  });
  els.reportDate.value = (snapshots[0] && snapshots[0].report_date) || state.data.latest.report_date;
  state.selectedDate = els.reportDate.value;
}
function currentReport() {
  const latest = state.data.latest || state.data;
  return state.currentReport || latest;
}

async function loadSelectedReport() {
  const date = state.selectedDate || (state.data.latest && state.data.latest.report_date);
  if (!date) {
    state.currentReport = state.data.latest || state.data;
    render();
    return;
  }
  const resp = await fetch(`./data/daily/${date}.json`, { cache: 'no-store' });
  state.currentReport = await resp.json();
  render();
}
function filterReports() {
  const q = state.query.trim().toLowerCase();
  const reports = currentReport().reports || [];
  if (!q) return reports;
  return reports.filter(r =>
    [r.argument_id, r.theme, r.core, ...(r.supporting_points || []), ...(r.sources || []).map(s => s.title || '')]
      .join(' ')
      .toLowerCase()
      .includes(q)
  );
}
function render() {
  if (!state.data) return;
  const current = currentReport();
  els.generatedAt.textContent = current.generated_at || '-';
  els.argumentCount.textContent = current.mention_count ?? '-';
  els.themeCount.textContent = current.theme_count ?? '-';
  els.reportMeta.textContent = `報告日 ${current.report_date || '-'} · 共 ${current.reports?.length || 0} 筆論點`;
  els.dailySummary.innerHTML = `
    <p class="muted">這是每日規則式整理結果。可用搜尋直接找主題、論點或來源標題。</p>
    <p>當前資料庫中共有 <strong>${current.mention_count || 0}</strong> 則整理內容，涵蓋 <strong>${current.theme_count || 0}</strong> 個主題。</p>
    <p class="muted">更新時間以 pipeline 完成時間為準，會隨每日排程自動改寫。</p>
  `;
  const reports = filterReports();
  els.reportList.innerHTML = reports.map(report => `
    <article class="card">
      <div class="tag">${report.theme} · ${report.argument_id}</div>
      <h3>${report.core}</h3>
      <p class="muted">出現次數 ${report.count} 次</p>
      <p>${(report.supporting_points || []).map(x => `• ${x}`).join('<br>') || '<span class="muted">尚無補充句</span>'}</p>
      <div class="sources">
        ${(report.sources || []).map(src => `<a href="${src.url}" target="_blank" rel="noreferrer">${src.title || src.url}</a>`).join('')}
      </div>
    </article>
  `).join('') || '<div class="card"><p class="muted">沒有符合條件的報告。</p></div>';
}
els.reportDate.addEventListener('change', e => {
  state.selectedDate = e.target.value;
  loadSelectedReport();
});
els.searchBox.addEventListener('input', e => {
  state.query = e.target.value;
  render();
});
loadData();
"""

    ensure_dir(docs_dir / "assets")
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    (docs_dir / "assets" / "site.css").write_text(site_css.strip() + "\n", encoding="utf-8")
    (docs_dir / "assets" / "site.js").write_text(site_js.strip() + "\n", encoding="utf-8")


def build_site_payload(mentions: list[Mention]) -> dict:
    theme_counter = Counter(m.topic_tag for m in mentions)
    arg_groups = defaultdict(list)
    for m in mentions:
        arg_groups[m.argument_id].append(m)

    reports = []
    for argument_id, group in sorted(arg_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        sample = group[0]
        sentences = []
        for item in group:
            sentences.extend(split_sentences(item.clean_content))
        freq = Counter(sentences)
        reports.append(
            {
                "argument_id": argument_id,
                "theme": sample.topic_tag,
                "count": len(group),
                "core": sample.clean_content[:180],
                "supporting_points": [s for s, _ in freq.most_common(3)],
                "sources": [{"title": m.title, "url": m.source_url, "published_at": m.published_at} for m in group],
            }
        )

    latest_update = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "generated_at": latest_update,
        "mention_count": len(mentions),
        "theme_count": len(theme_counter),
        "theme_counts": dict(theme_counter.most_common()),
        "reports": reports,
    }


def write_site_files(site_data: dict, docs_dir: Path) -> None:
    data_dir = docs_dir / "data"
    report_dir = data_dir / "reports"
    ensure_dir(report_dir)
    save_json(data_dir / "index.json", site_data)
    for report in site_data.get("reports", []):
        save_json(report_dir / f"{report['argument_id']}.json", report)

    index_html = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="股癌分析專區，依日期查看每日論點整理與更新紀錄。" />
  <title>股癌分析專區</title>
  <link rel="stylesheet" href="./assets/site.css" />
</head>
<body>
  <div class="page-shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Topic 22 / Stockguy Analysis</p>
        <h1>股癌分析專區</h1>
        <p class="lead">每日自動抓取、整理與歸納公開言論，按日期切換報告，保留來源可追溯。</p>
      </div>
      <div class="hero-metrics">
        <div class="metric">
          <span class="metric-label">最後更新</span>
          <strong id="generatedAt">-</strong>
        </div>
        <div class="metric">
          <span class="metric-label">論點數</span>
          <strong id="argumentCount">-</strong>
        </div>
        <div class="metric">
          <span class="metric-label">主題數</span>
          <strong id="themeCount">-</strong>
        </div>
      </div>
    </header>

    <main class="layout">
      <section class="panel controls">
        <div class="control-row">
          <label for="reportDate">選擇日期</label>
          <select id="reportDate"></select>
        </div>
        <div class="control-row">
          <label for="searchBox">搜尋論點</label>
          <input id="searchBox" type="search" placeholder="輸入關鍵字，例如 AI、風控、半導體" />
        </div>
      </section>

      <section class="panel summary">
        <div class="section-head">
          <h2>日期報告</h2>
          <span id="reportMeta" class="meta-pill"></span>
        </div>
        <article id="dailySummary" class="summary-card"></article>
      </section>

      <section class="panel">
        <div class="section-head">
          <h2>論點卡片</h2>
          <span class="meta-pill">可點來源追回原文</span>
        </div>
        <div id="reportList" class="cards"></div>
      </section>
    </main>
  </div>
  <script src="./assets/site.js"></script>
</body>
</html>
"""

    site_css = """
:root {
  color-scheme: dark;
  --bg: #0b1020;
  --panel: rgba(13, 18, 35, 0.82);
  --panel-border: rgba(173, 193, 255, 0.12);
  --text: #e8ecff;
  --muted: #97a2c6;
  --accent: #8dd6ff;
  --accent-2: #ffd166;
  --good: #7cf0b7;
  --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(141, 214, 255, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(255, 209, 102, 0.12), transparent 25%),
    linear-gradient(180deg, #0b1020 0%, #0d1328 100%);
  color: var(--text);
}
.page-shell { max-width: 1280px; margin: 0 auto; padding: 32px 20px 48px; }
.hero {
  display: grid; gap: 24px;
  grid-template-columns: 1.6fr 1fr;
  align-items: end;
  margin-bottom: 24px;
}
.eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .18em; font-size: 12px; }
h1 { font-size: clamp(2.8rem, 6vw, 5rem); margin: 0 0 8px; line-height: .95; }
.lead { max-width: 62ch; color: var(--muted); font-size: 1.05rem; }
.hero-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.metric, .panel, .summary-card {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  box-shadow: var(--shadow);
  backdrop-filter: blur(18px);
  border-radius: 20px;
}
.metric { padding: 16px; }
.metric-label, .meta-pill, label { color: var(--muted); font-size: 12px; }
.metric strong { display: block; font-size: 1.6rem; margin-top: 6px; }
.layout { display: grid; gap: 18px; }
.panel { padding: 18px; }
.controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.control-row { display: grid; gap: 8px; }
select, input {
  width: 100%; padding: 14px 15px; border-radius: 14px;
  background: rgba(255,255,255,.04); color: var(--text);
  border: 1px solid rgba(255,255,255,.12); outline: none;
}
.section-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.meta-pill { padding: 8px 12px; border-radius: 999px; background: rgba(141, 214, 255, 0.08); }
.summary-card { padding: 18px; min-height: 120px; }
.cards { display: grid; gap: 14px; }
.card {
  padding: 18px; border-radius: 18px;
  background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
  border: 1px solid rgba(255,255,255,.08);
}
.card h3 { margin: 0 0 8px; font-size: 1.1rem; }
.card .tag { color: var(--accent-2); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
.sources { margin-top: 14px; display: grid; gap: 8px; }
.sources a { color: var(--accent); text-decoration: none; }
.muted { color: var(--muted); }
@media (max-width: 900px) {
  .hero, .controls, .hero-metrics { grid-template-columns: 1fr; }
}
"""

    site_js = """
const state = {
  data: null,
  selectedDate: null,
  query: ""
};

const els = {
  generatedAt: document.getElementById('generatedAt'),
  argumentCount: document.getElementById('argumentCount'),
  themeCount: document.getElementById('themeCount'),
  reportDate: document.getElementById('reportDate'),
  searchBox: document.getElementById('searchBox'),
  reportMeta: document.getElementById('reportMeta'),
  dailySummary: document.getElementById('dailySummary'),
  reportList: document.getElementById('reportList')
};

async function loadData() {
  const resp = await fetch('./data/index.json', { cache: 'no-store' });
  state.data = await resp.json();
  renderDateOptions();
  render();
}

function renderDateOptions() {
  const option = document.createElement('option');
  option.value = 'today';
  option.textContent = '最新報告';
  els.reportDate.appendChild(option);
  els.reportDate.value = 'today';
  state.selectedDate = 'today';
}

function filterReports() {
  const q = state.query.trim().toLowerCase();
  const reports = state.data?.reports || [];
  if (!q) return reports;
  return reports.filter(r =>
    [r.argument_id, r.theme, r.core, ...(r.supporting_points || []), ...(r.sources || []).map(s => s.title || '')]
      .join(' ')
      .toLowerCase()
      .includes(q)
  );
}

function render() {
  if (!state.data) return;
  els.generatedAt.textContent = state.data.generated_at || '-';
  els.argumentCount.textContent = state.data.mention_count ?? '-';
  els.themeCount.textContent = state.data.theme_count ?? '-';
  els.reportMeta.textContent = `共 ${state.data.reports?.length || 0} 筆論點`;

  els.dailySummary.innerHTML = `
    <p class="muted">這是每日規則式整理結果。可用搜尋直接找主題、論點或來源標題。</p>
    <p>當前資料庫中共有 <strong>${state.data.mention_count || 0}</strong> 則整理內容，涵蓋 <strong>${state.data.theme_count || 0}</strong> 個主題。</p>
    <p class="muted">更新時間以 pipeline 完成時間為準，會隨每日排程自動改寫。</p>
  `;

  const reports = filterReports();
  els.reportList.innerHTML = reports.map(report => `
    <article class="card">
      <div class="tag">${report.theme} · ${report.argument_id}</div>
      <h3>${report.core}</h3>
      <p class="muted">出現次數 ${report.count} 次</p>
      <p>${(report.supporting_points || []).map(x => `• ${x}`).join('<br>') || '<span class="muted">尚無補充句</span>'}</p>
      <div class="sources">
        ${(report.sources || []).map(src => `<a href="${src.url}" target="_blank" rel="noreferrer">${src.title || src.url}</a>`).join('')}
      </div>
    </article>
  `).join('') || '<div class="card"><p class="muted">沒有符合條件的報告。</p></div>';
}

els.searchBox.addEventListener('input', e => {
  state.query = e.target.value;
  render();
});

loadData();
"""

    ensure_dir(docs_dir / "assets")
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    (docs_dir / "assets" / "site.css").write_text(site_css.strip() + "\n", encoding="utf-8")
    (docs_dir / "assets" / "site.js").write_text(site_js.strip() + "\n", encoding="utf-8")


def main() -> int:
    config = load_json(ROOT / "config.json", {})
    keywords = load_json(ROOT / config.get("keywords_file", "project_data/keywords.json"), {"themes": {}})
    theme_map = keywords.get("themes", {})
    sources = load_json(ROOT / config.get("sources_file", "project_data/sources.json"), {}).get("sources", [])

    input_dir = ROOT / config.get("input_dir", "project_data/raw")
    clean_dir = ROOT / config.get("clean_dir", "project_data/cleaned")
    output_dir = ROOT / config.get("output_dir", "output")
    reports_dir = ROOT / config.get("reports_dir", "output/reports")
    daily_report_file = ROOT / config.get("daily_report_file", "output/daily_report.md")
    weekly_report_file = ROOT / config.get("weekly_report_file", "output/weekly_report.md")
    benchmark_dir = ROOT / config.get("benchmark_dir", "project_data/benchmarks")
    company_master_path = ROOT / config.get("benchmark_source_company_master", "../topic_06_self_assessed_eps_catalyst/project_data/full_market_base/full_market_base.csv")
    price_dir = ROOT / config.get("benchmark_source_price_dir", "../topic_06_self_assessed_eps_catalyst/project_data/full_market_prices/prices")
    benchmark_design = load_json(ROOT / config.get("benchmark_design_file", "project_data/benchmark_design.json"), {})

    for source in sources:
        if not source.get("enabled", False):
            continue
        collected = collect_from_source(source)
        if collected:
            save_raw_mentions(input_dir, collected, str(source.get("name", "source")))

    raw = load_raw_mentions(input_dir)
    mentions = [coerce_mention(obj, theme_map) for obj in raw]
    mentions = dedupe_mentions(mentions)

    mention_rows = [m.__dict__ for m in mentions]
    write_csv(
        clean_dir / "mentions.csv",
        mention_rows,
        ["source_id", "source_type", "source_url", "published_at", "author", "title", "content", "clean_content", "topic_tag", "argument_id", "confidence"],
    )

    arg_summary = defaultdict(list)
    for m in mentions:
        arg_summary[m.argument_id].append(m)

    argument_rows = []
    for argument_id, group in arg_summary.items():
        representative = group[0]
        theme = representative.topic_tag
        sentences = []
        for item in group:
            sentences.extend(split_sentences(item.clean_content))
        freq = Counter(sentences)
        argument_rows.append(
            {
                "argument_id": argument_id,
                "theme": theme,
                "argument_summary": group[0].clean_content[:200],
                "supporting_points": " | ".join(s for s, _ in freq.most_common(3)),
                "assumptions": "待人工補強",
                "risk_points": "待人工補強",
                "related_sources": " | ".join(m.source_url for m in group if m.source_url),
            }
        )

    write_csv(
        output_dir / "arguments.csv",
        argument_rows,
        ["argument_id", "theme", "argument_summary", "supporting_points", "assumptions", "risk_points", "related_sources"],
    )

    theme_rows = [
        {"theme": theme, "count": count}
        for theme, count in Counter(m.topic_tag for m in mentions).most_common()
    ]
    write_csv(output_dir / "themes.csv", theme_rows, ["theme", "count"])

    weekly_analysis = build_weekly_analysis(mentions, theme_map)
    design_dynamic_benchmarks(weekly_analysis, benchmark_dir, company_master_path, price_dir, benchmark_design)
    accuracy_report = build_accuracy_report(weekly_analysis, benchmark_dir)

    report = generate_report(mentions)
    site_data = build_site_payload(mentions)
    reports_dir.mkdir(parents=True, exist_ok=True)
    daily_report_file.parent.mkdir(parents=True, exist_ok=True)
    daily_report_file.write_text(report, encoding="utf-8")
    write_weekly_report(weekly_analysis, accuracy_report, weekly_report_file)
    (reports_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.md").write_text(report, encoding="utf-8")
    write_site_files(site_data, ROOT / "docs")

    save_json(clean_dir / "run_summary.json", {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mention_count": len(mentions),
        "theme_count": len(theme_rows),
        "weekly_count": len(weekly_analysis),
        "accuracy_samples": accuracy_report["total_weeks"],
        "accuracy_rate": accuracy_report["accuracy"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
