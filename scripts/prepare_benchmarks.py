from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BenchmarkSpec:
    name: str
    label: str
    source_file: str


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_number(value):
    text = str(value or "").strip().replace(",", "")
    if not text or text in {"-", "--", "NA", "N/A"}:
        return ""
    try:
        return float(text)
    except ValueError:
        return ""


def read_source(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def write_standard(path: Path, rows: list[dict]) -> None:
    ensure_dir(path.parent)
    fieldnames = ["trade_date", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        trade_date = row.get("trade_date") or row.get("date") or row.get("day")
        if not trade_date:
            continue
        out.append(
            {
                "trade_date": trade_date,
                "open": normalize_number(row.get("open")),
                "high": normalize_number(row.get("high")),
                "low": normalize_number(row.get("low")),
                "close": normalize_number(row.get("close")),
                "volume": normalize_number(row.get("volume")),
            }
        )
    return out


def main() -> int:
    source_dir = ROOT / "project_data" / "benchmark_sources"
    target_dir = ROOT / "project_data" / "benchmarks"
    ensure_dir(source_dir)
    ensure_dir(target_dir)

    manifest = []
    for source_path in sorted(source_dir.glob("*.csv")):
        spec = BenchmarkSpec(name=source_path.stem, label=source_path.stem, source_file=source_path.name)
        target_path = target_dir / source_path.name
        if not source_path.exists():
            manifest.append({"name": spec.name, "label": spec.label, "source_file": spec.source_file, "status": "missing"})
            continue
        rows = build_rows(read_source(source_path))
        write_standard(target_path, rows)
        manifest.append({"name": spec.name, "label": spec.label, "source_file": spec.source_file, "status": "written", "rows": len(rows)})

    (target_dir / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
