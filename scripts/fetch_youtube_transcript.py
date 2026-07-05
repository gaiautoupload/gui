from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi


ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch the latest Gooaye YouTube transcript.")
    parser.add_argument("--video-id", default="", help="YouTube video id. Defaults to the first row in --latest-from.")
    parser.add_argument(
        "--latest-from",
        default="project_data/episode_monitor/youtube_channel_episodes.csv",
        help="CSV produced by stockguy_pipeline.py YouTube feed monitoring.",
    )
    parser.add_argument("--output-dir", default="project_data/transcripts")
    parser.add_argument("--analysis-input-dir", default="project_data/analysis_inputs")
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["zh-Hant", "zh-TW", "zh-Hans", "zh", "en"],
        help="Transcript language preference order.",
    )
    parser.add_argument("--allow-missing", action="store_true", help="Return success when subtitles are unavailable.")
    return parser.parse_args()


def load_latest_video(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing monitor CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Monitor CSV has no rows: {path}")
    return rows[0]


def video_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/")
    query_id = parse_qs(parsed.query).get("v", [""])[0]
    if query_id:
        return query_id
    match = re.search(r"(?:embed|shorts)/([A-Za-z0-9_-]{8,})", parsed.path)
    return match.group(1) if match else ""


def safe_stem(text: str) -> str:
    stem = re.sub(r"[^\w.-]+", "_", text, flags=re.UNICODE).strip("_")
    return stem[:80] or "youtube_transcript"


def date_prefix(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        return match.group(0) if match else datetime.now().strftime("%Y-%m-%d")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def transcript_rows(transcript) -> list[dict]:
    if hasattr(transcript, "to_raw_data"):
        return transcript.to_raw_data()
    rows = []
    for item in transcript:
        if isinstance(item, dict):
            rows.append(item)
        else:
            rows.append({"text": item.text, "start": item.start, "duration": item.duration})
    return rows


def write_analysis_input(path: Path, metadata: dict, rows: list[dict]) -> None:
    lines = [
        f"# 股癌 YouTube 逐字稿：{metadata.get('title', '')}",
        "",
        f"- source_url: {metadata.get('url', '')}",
        f"- published_at: {metadata.get('published_at', '')}",
        f"- video_id: {metadata.get('video_id', '')}",
        "- analysis_ready: true",
        "",
        "## Transcript",
        "",
    ]
    lines.extend(str(row.get("text", "")).strip() for row in rows if str(row.get("text", "")).strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def compact_error_message(exc: Exception) -> str:
    if exc.__class__.__name__ == "TranscriptsDisabled":
        return "Subtitles are disabled for this video."
    for line in str(exc).splitlines():
        line = line.strip()
        if line:
            return line
    return exc.__class__.__name__


def main() -> int:
    args = parse_args()
    latest_path = ROOT / args.latest_from
    latest = load_latest_video(latest_path)
    video_id = args.video_id or video_id_from_url(latest.get("url", ""))
    if not video_id:
        raise ValueError("Could not resolve YouTube video id.")

    metadata = {
        "video_id": video_id,
        "title": latest.get("title", ""),
        "url": latest.get("url", f"https://www.youtube.com/watch?v={video_id}"),
        "published_at": latest.get("published_at", ""),
        "languages": args.languages,
    }
    output_dir = ROOT / args.output_dir
    stem = f"{date_prefix(metadata['published_at'])}_{safe_stem(metadata['title'])}_{video_id}"
    status_path = output_dir / "latest_status.json"

    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=args.languages, preserve_formatting=False)
        rows = transcript_rows(transcript)
    except Exception as exc:
        status = {
            "status": "missing",
            **metadata,
            "error_type": exc.__class__.__name__,
            "message": compact_error_message(exc),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        write_json(status_path, status)
        print(json.dumps(status, ensure_ascii=True))
        return 0 if args.allow_missing else 2

    transcript_payload = {
        "status": "ready",
        **metadata,
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "row_count": len(rows),
        "transcript": rows,
    }
    json_path = output_dir / f"{stem}.json"
    txt_path = output_dir / f"{stem}.txt"
    analysis_path = ROOT / args.analysis_input_dir / f"{stem}.md"
    write_json(json_path, transcript_payload)
    txt_path.write_text("\n".join(row.get("text", "") for row in rows).strip() + "\n", encoding="utf-8")
    write_analysis_input(analysis_path, metadata, rows)
    write_json(status_path, {k: v for k, v in transcript_payload.items() if k != "transcript"} | {"analysis_input": str(analysis_path.relative_to(ROOT))})
    print(json.dumps({"status": "ready", "video_id": video_id, "analysis_input": str(analysis_path)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
