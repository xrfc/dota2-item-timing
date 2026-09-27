"""Small CLI: cached API input and offline reports share the same pipeline."""

import argparse
import json
import sys
from pathlib import Path

from .analysis import analyze
from .normalize import load_timeline
from .report import render_html
from .sources.opendota import fetch_match


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DOTA2 item purchase record analysis")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Cache one OpenDota match")
    fetch.add_argument("match_id", type=int)
    fetch.add_argument("--cache-dir", type=Path, default=Path("data/raw"))
    fetch.add_argument("--refresh", action="store_true")
    report = commands.add_parser("report", help="Analyze cached match JSON")
    report.add_argument("input", type=Path)
    report.add_argument("--player-slot", type=int, required=True)
    report.add_argument("--config", type=Path, default=Path("configs/analysis.json"))
    report.add_argument("--output", type=Path, default=Path("reports/latest"))
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            destination = fetch_match(args.match_id, args.cache_dir, refresh=args.refresh)
            print(json.dumps({"cached_match": str(destination)}, ensure_ascii=False))
            return 0
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Configuration must be an object")
        items = config.get("candidate_items")
        if (
            not isinstance(items, list)
            or not items
            or any(not isinstance(item, str) or not item.strip() for item in items)
        ):
            raise ValueError("candidate_items must contain non-empty item keys")
        timeline = load_timeline(args.input, args.player_slot)
        result = analyze(timeline, items)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "analysis.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        (args.output / "report.html").write_text(render_html(result), encoding="utf-8")
        print(json.dumps({"report": str(args.output / "report.html")}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
