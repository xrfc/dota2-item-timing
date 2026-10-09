"""Snapshot Valve hero descriptions without inferring game mechanics."""

import concurrent.futures
import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources"
SOURCES.mkdir(exist_ok=True)


def fetch(hero_id, language):
    url = f"https://www.dota2.com/datafeed/herodata?language={language}&hero_id={hero_id}"
    path = SOURCES / f"hero-{hero_id}-{language}.json"
    # Existing valid snapshots are immutable within this run.
    if path.exists():
        payload = path.read_bytes()
        downloaded = False
    else:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=35) as response:
                    payload = response.read()
                heroes = json.loads(payload)["result"]["data"]["heroes"]
                if len(heroes) != 1 or heroes[0]["id"] != hero_id:
                    raise ValueError("Unexpected hero response identity")
                path.write_bytes(payload)
                downloaded = True
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
    heroes = json.loads(payload)["result"]["data"]["heroes"]
    if len(heroes) != 1 or heroes[0]["id"] != hero_id:
        raise ValueError(f"Unexpected saved identity: {path}")
    return {
        "hero_id": hero_id,
        "language": language,
        "url": url,
        "file": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "snapshot_observed_at_utc": datetime.now(UTC).isoformat(),
        "downloaded_this_run": downloaded,
    }


def main():
    heroes = json.loads((SOURCES / "herolist-english.json").read_text(encoding="utf-8"))["result"][
        "data"
    ]["heroes"]
    tasks = [(hero["id"], language) for hero in heroes for language in ("english", "schinese")]
    records, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(fetch, *task): task for task in tasks}
        for future in concurrent.futures.as_completed(jobs):
            try:
                records.append(future.result())
            except Exception as exc:
                errors.append({"task": jobs[future], "error": str(exc)})
            if (len(records) + len(errors)) % 25 == 0:
                print(f"{len(records)} snapshots saved; {len(errors)} errors", flush=True)
    records.sort(key=lambda row: (row["hero_id"], row["language"]))
    manifest = {
        "schema": "hero-source-manifest/1",
        "learning_scope": "current_official_snapshot",
        "target_patch": None,
        "historical_adaptation": "deferred",
        "source_patch": None,
        "patch_verified": False,
        "note": (
            "Current official website snapshot; no patch identifier supplied by these endpoints. "
            "Not admitted for historical replay conclusions."
        ),
        "expected_heroes": len(heroes),
        "expected_detail_files": len(tasks),
        "records": records,
        "errors": errors,
    }
    for name in ("herolist-english.json", "herolist-schinese.json", "opendota-heroes.json"):
        path = SOURCES / name
        if path.exists():
            manifest.setdefault("catalog_files", []).append(
                {"file": f"sources/{name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
    (ROOT / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"saved": len(records), "errors": errors}, ensure_ascii=False), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
