"""Collect a bounded, provenance-preserving cohort of public ranked replays.

External acquisition failures produce an incomplete report; they are never acceptance passes.
Run this opt-in command separately from offline unit tests.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from dota_items.data.acceptance import audit_prepared
from dota_items.sources.opendota import fetch_match
from dota_items.storage import file_hash, now, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/acceptance/7.41f.json"))
    parser.add_argument("--output", type=Path, default=Path("data/acceptance"))
    args = parser.parse_args()
    root = args.output
    config = json.loads(args.config.read_text())
    report = {
        "schema_version": "real-acceptance/1",
        "started_at": now(),
        "config": config,
        "results": [],
        "status": "collecting",
    }
    client = httpx.Client(timeout=45, follow_redirects=True)
    total_bytes = 0
    downloaded = 0
    deadline = time.monotonic() + 2700

    def save():
        write_json(root / "report.json", report)

    def get_json(url, name):
        time.sleep(1.1)
        response = client.get(url)
        response.raise_for_status()
        result = response.json()
        write_json(root / name, result)
        return result

    try:
        url = "https://www.dota2.com/datafeed/patchnoteslist?language=english"
        patches = get_json(url, "patchnotes.json")["patches"]
        patch = next(p for p in patches if p["patch_number"] == config["patch"])
        lower = patch["patch_timestamp"] + config["patch_boundary_buffer_seconds"]
        upper = min(
            [
                p["patch_timestamp"]
                for p in patches
                if p["patch_timestamp"] > patch["patch_timestamp"]
            ]
            + [int(time.time())]
        )
        report["patch_evidence"] = {
            "source": url,
            "lower_inclusive": lower,
            "upper_exclusive": upper,
            "confidence": "time_inferred",
        }
        candidates = {}
        before = ""
        for page in range(config["discovery_pages"]):
            url = "https://api.opendota.com/api/publicMatches?min_rank=75" + before
            matches = get_json(url, f"public-{page}.json")
            if not matches:
                break
            for match in matches:
                if (
                    (match.get("avg_rank_tier") or 0) >= config["minimum_average_rank_tier"]
                    and (match.get("num_rank_tier") or 0) >= config["minimum_ranked_players"]
                    and match.get("game_mode") == 22
                    and match.get("lobby_type") == 7
                ):
                    candidates[match["match_id"]] = match
            before = "&less_than_match_id=" + str(min(m["match_id"] for m in matches))
            if len(candidates) >= config["max_candidates"]:
                break
        report["discovered"] = len(candidates)
        save()
        ordered = sorted(candidates.values(), key=lambda r: (-r["num_rank_tier"], -r["match_id"]))
        for candidate in ordered[: config["max_candidates"]]:
            if (
                downloaded >= config["target_downloads"]
                or time.monotonic() > deadline
                or total_bytes >= config["max_total_download_bytes"]
            ):
                break
            match_id = candidate["match_id"]
            row = {"match_id": match_id, "rank_evidence": candidate, "status": "candidate"}
            report["results"].append(row)
            save()
            try:
                start = candidate.get("start_time", 0)
                duration = candidate.get("duration", 0)
                if not lower <= start < start + duration < upper:
                    raise ValueError("outside requested letter-patch time interval")
                if (
                    not config["minimum_duration_seconds"]
                    <= duration
                    <= config["maximum_duration_seconds"]
                ):
                    raise ValueError("duration outside acceptance cohort")
                time.sleep(1.1)
                api_path = fetch_match(match_id, root / "metadata", client=client)
                api = json.loads(api_path.read_text())
                if api.get("start_time") != start or api.get("duration") != duration:
                    raise ValueError("public listing and match metadata disagree")
                if api.get("game_mode") != 22 or api.get("lobby_type") != 7:
                    raise ValueError("not standard ranked All Pick")
                replay_url = api.get("replay_url")
                if not replay_url:
                    raise ValueError("OpenDota has no public replay_url")
                parsed = urlsplit(replay_url)
                if parsed.scheme not in ("http", "https") or not any(
                    (parsed.hostname or "").endswith("." + host)
                    for host in (
                        "valve.net",
                        "steamcontent.com",
                        "valveusercontent.com",
                        "dota2.com.cn",
                    )
                ):
                    raise ValueError("unexpected public replay host")
                row["replay_url"] = replay_url
                replay = root / "replays" / f"{match_id}.dem.bz2"
                replay.parent.mkdir(exist_ok=True)
                size = 0
                try:
                    with client.stream("GET", replay_url, timeout=120) as response:
                        response.raise_for_status()
                        with replay.open("wb") as output:
                            for chunk in response.iter_bytes(1024**2):
                                size += len(chunk)
                                total_bytes += len(chunk)
                                if (
                                    size > config["max_archive_bytes"]
                                    or total_bytes > config["max_total_download_bytes"]
                                ):
                                    raise ValueError("download byte budget exceeded")
                                output.write(chunk)
                except Exception:
                    replay.unlink(missing_ok=True)
                    raise
                downloaded += 1
                row.update(
                    status="downloaded", archive_bytes=size, archive_sha256=file_hash(replay)
                )
                save()
                print(f"Downloaded {match_id}: {size} bytes; preparing", flush=True)
                workspace = root / "workspaces" / str(match_id)
                log = root / f"{match_id}.prepare.log"
                started = time.monotonic()
                with log.open("w") as stream:
                    process = subprocess.run(
                        [
                            sys.executable,
                            "coach.py",
                            "--workspace",
                            str(workspace),
                            "prepare",
                            str(replay),
                        ],
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        timeout=config["parse_timeout_seconds"],
                        check=False,
                    )
                row.update(
                    prepare_exit_code=process.returncode, prepare_seconds=time.monotonic() - started
                )
                batches = sorted((workspace / "imports").glob("prepare-*.json"))
                row["preparation"] = json.loads(batches[-1].read_text()) if batches else None
                row["status"] = "prepared" if process.returncode == 0 else "preparation_failed"
                exports = root / "exports" / str(match_id)
                exports.mkdir(parents=True, exist_ok=True)
                for folder in (workspace / "prepared").glob("*"):
                    for name in (
                        "cleaned.json",
                        "quality.json",
                        "manifest.json",
                        "features.jsonl",
                        "labels.jsonl",
                        "trace.jsonl",
                    ):
                        source = folder / name
                        if source.is_file():
                            shutil.copyfile(source, exports / name)
                if row["status"] == "prepared":
                    prepared = Path(row["preparation"]["results"][0]["path"])
                    row["audit"] = audit_prepared(prepared, api)
                    write_json(exports / "audit.json", row["audit"])
                print(f"Result {match_id}: {row['status']}", flush=True)
            except (ValueError, httpx.HTTPError, OSError, subprocess.TimeoutExpired) as error:
                row.update(status="failed", error_type=type(error).__name__, error=str(error))
                print(f"Unavailable {match_id}: {row['error']}", flush=True)
            save()
    except (ValueError, httpx.HTTPError, OSError) as error:
        report["blocking_error"] = str(error)
    finally:
        client.close()
        report.update(
            finished_at=now(),
            downloaded=downloaded,
            download_bytes=total_bytes,
            status="collected" if downloaded == config["target_downloads"] else "incomplete",
            training_admission="see_per_match_audit",
        )
        save()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
