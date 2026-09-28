"""Small CLI: cached API input and offline reports share the same pipeline."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .analysis import analyze
from .normalize import load_timeline
from .report import render_html
from .sources.gem_replay import ingest_demo
from .sources.opendota import fetch_match


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DOTA2 item purchase record analysis")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Cache one OpenDota match")
    fetch.add_argument("match_id", type=int)
    fetch.add_argument("--cache-dir", type=Path, default=Path("data/raw"))
    fetch.add_argument("--refresh", action="store_true")
    ingest = commands.add_parser(
        "ingest-demo", help="Parse local DOTA2 replay(s) and initialize data"
    )
    ingest.add_argument("input", type=Path, help="A .dem/.dem.bz2/.dem.zst/.dem.zip or a folder")
    ingest.add_argument("--data-dir", type=Path, default=Path("data"))
    ingest.add_argument(
        "--recursive", action="store_true", help="Scan subfolders when input is a folder"
    )
    ingest.add_argument("--force", action="store_true", help="Reparse already indexed replays")
    status = commands.add_parser("data-status", help="Show local replay index counts")
    status.add_argument("--data-dir", type=Path, default=Path("data"))
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
        if args.command == "data-status":
            database = args.data_dir / "index.sqlite"
            if not database.is_file():
                raise ValueError(f"No replay index found: {database}")
            with sqlite3.connect(database) as index:
                summary = {
                    "matches": index.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
                    "players": index.execute("SELECT COUNT(*) FROM players").fetchone()[0],
                    "item_events": index.execute("SELECT COUNT(*) FROM item_events").fetchone()[0],
                    "match_ids": [
                        row[0]
                        for row in index.execute(
                            "SELECT DISTINCT match_id FROM matches ORDER BY match_id"
                        )
                    ],
                }
            print(json.dumps(summary, ensure_ascii=False))
            return 0
        if args.command == "ingest-demo":
            if args.input.is_file():
                sources = [args.input]
            elif args.input.is_dir():
                candidates = args.input.rglob("*") if args.recursive else args.input.iterdir()
                sources = sorted(
                    path
                    for path in candidates
                    if path.is_file()
                    and path.name.lower().endswith((".dem", ".dem.bz2", ".dem.zst", ".dem.zip"))
                )
            else:
                raise ValueError(f"Replay input does not exist: {args.input}")
            if not sources:
                raise ValueError("No supported DOTA2 replay files found")
            failures = 0
            for source in sources:
                print(f"Parsing {source} ...", file=sys.stderr)
                try:
                    result = ingest_demo(source, args.data_dir, force=args.force)
                    print(json.dumps(result, ensure_ascii=False))
                except Exception as error:
                    # Isolate one failed replay so a batch still imports the rest.
                    failures += 1
                    print(
                        json.dumps(
                            {"status": "error", "source": str(source), "error": str(error)},
                            ensure_ascii=False,
                        ),
                        file=sys.stderr,
                    )
            return 1 if failures else 0
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
