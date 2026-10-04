"""Offline replay adapter. Gem types never cross this module boundary."""

import bz2
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from ..normalize import normalize_match
from ..storage import file_hash
from .gem_observations import number, observations

MAX_DEMO_BYTES = 2 * 1024**3
CHUNK_BYTES = 1024**2
DEMO_MAGIC = b"PBDEMS2"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
ADAPTER_VERSION = "gem-adapter/2.0"


def _copy_bounded(source: Any, target: Any) -> None:
    total = 0
    while chunk := source.read(CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_DEMO_BYTES:
            raise ValueError("Decompressed replay exceeds the 2 GiB safety limit")
        target.write(chunk)


@contextmanager
def prepared_demo(source: Path, scratch_dir: Path) -> Iterator[Path]:
    """Accept raw .dem, .dem.bz2/.zst, or a ZIP containing one .dem."""
    if not source.is_file():
        raise ValueError(f"Replay file does not exist: {source}")
    name = source.name.lower()
    if name.endswith(".dem"):
        if source.stat().st_size > MAX_DEMO_BYTES:
            raise ValueError("Replay exceeds the 2 GiB safety limit")
        with source.open("rb") as stream:
            if stream.read(len(DEMO_MAGIC)) != DEMO_MAGIC:
                raise ValueError("Replay is not a Source 2 PBDEMS2 .dem file")
        yield source
        return
    if not name.endswith((".dem.bz2", ".dem.zst", ".dem.zip")):
        raise ValueError("Supported replay files: .dem, .dem.bz2, .dem.zst, .dem.zip")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_dir, prefix="replay-") as temporary:
        unpacked = Path(temporary) / "match.dem"
        if name.endswith(".dem.zip"):
            with zipfile.ZipFile(source) as archive:
                members = [
                    member
                    for member in archive.infolist()
                    if member.filename.lower().endswith(".dem") and not member.is_dir()
                ]
                if len(members) != 1:
                    raise ValueError("ZIP must contain exactly one .dem file")
                if members[0].file_size > MAX_DEMO_BYTES:
                    raise ValueError("Decompressed replay exceeds the 2 GiB safety limit")
                with archive.open(members[0]) as replay, unpacked.open("wb") as output:
                    _copy_bounded(replay, output)
        else:
            with source.open("rb") as compressed:
                magic = compressed.read(4)
            if magic.startswith(b"BZh"):
                with bz2.open(source, "rb") as replay, unpacked.open("wb") as output:
                    _copy_bounded(replay, output)
            elif magic == ZSTD_MAGIC:
                try:
                    import zstandard
                except ImportError as error:
                    raise ValueError(
                        "Zstandard support requires pip install -e '.[replay]'"
                    ) from error
                with source.open("rb") as compressed, unpacked.open("wb") as output:
                    with zstandard.ZstdDecompressor().stream_reader(compressed) as replay:
                        _copy_bounded(replay, output)
            else:
                raise ValueError("Unknown replay archive compression")
        with unpacked.open("rb") as stream:
            if stream.read(len(DEMO_MAGIC)) != DEMO_MAGIC:
                raise ValueError("Archive does not contain a Source 2 PBDEMS2 replay")
        yield unpacked


def _player_slot(player_id: int) -> int:
    if isinstance(player_id, bool) or not isinstance(player_id, int) or player_id not in range(10):
        raise ValueError(f"Gem returned an unsupported player_id: {player_id}")
    return player_id if player_id < 5 else 128 + player_id - 5


def canonicalize_match(match: Any) -> tuple[dict[str, Any], list[str]]:
    """Convert Gem's typed match into the existing OpenDota-shaped report input."""
    if not isinstance(match.match_id, int) or match.match_id <= 0:
        raise ValueError("Replay has no valid match_id; cannot initialize the match index")
    if not isinstance(match.duration, int) or match.duration < 0:
        raise ValueError("Replay has no valid game duration")
    if not match.players:
        raise ValueError("Replay contains no player summaries")
    players: list[dict[str, Any]] = []
    issues: list[str] = []
    slots: set[int] = set()
    for player_index, player in enumerate(match.players):
        slot = _player_slot(player.player_id)
        if slot in slots:
            raise ValueError(f"Replay contains duplicate player slot {slot}")
        slots.add(slot)
        if not isinstance(player.hero_id, int) or player.hero_id <= 0:
            issues.append(f"player {slot}: missing hero_id; omitted from normalized match")
            continue
        purchases: list[dict[str, Any]] = []
        for event_index, event in enumerate(player.purchase_log):
            name = event.value_name
            if not isinstance(name, str) or not name or name == "dota_unknown":
                issues.append(f"player {slot}: purchase with unknown item key")
                continue
            second = event.game_time_s
            if second is None and match.game_clock is not None:
                second = match.game_clock.game_seconds_at(event.tick)
            if second is None:
                issues.append(f"player {slot}: purchase time unavailable at tick {event.tick}")
                continue
            if not number(second) or second > match.duration:
                issues.append(f"player {slot}: purchase time outside match at tick {event.tick}")
                continue
            key = name.removeprefix("item_")
            if key.startswith("recipe_"):
                continue
            purchases.append(
                {
                    "time": second,
                    "key": key,
                    "source_tick": event.tick,
                    "source_ref": f"players[{player_index}].purchase_log[{event_index}]",
                }
            )
        players.append(
            {
                "player_slot": slot,
                "hero_id": player.hero_id,
                "purchase_log": purchases,
                **observations(player, player_index, match),
            }
        )
    if not players:
        raise ValueError("Replay has no players with valid hero IDs")
    if getattr(match, "post_game_tick", None) is None:
        issues.append("post_game_tick unavailable: replay may be incomplete")
    return {
        "schema_version": ADAPTER_VERSION,
        "match_id": match.match_id,
        "duration": match.duration,
        "game_mode": match.game_mode,
        "patch": None,
        "players": players,
        "adapter_issues": issues,
    }, issues


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS matches (
    source_sha256 TEXT PRIMARY KEY, match_id INTEGER NOT NULL, duration_seconds INTEGER NOT NULL,
    game_mode INTEGER, source_name TEXT NOT NULL, parser_version TEXT NOT NULL,
    raw_json TEXT NOT NULL, normalized_json TEXT NOT NULL,
    imported_at TEXT NOT NULL, issue_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
    source_sha256 TEXT NOT NULL REFERENCES matches(source_sha256),
    player_slot INTEGER NOT NULL, hero_id INTEGER NOT NULL,
    PRIMARY KEY (source_sha256, player_slot)
);
CREATE TABLE IF NOT EXISTS item_events (
    source_sha256 TEXT NOT NULL, player_slot INTEGER NOT NULL, ordinal INTEGER NOT NULL,
    item_key TEXT NOT NULL, time_seconds REAL NOT NULL, source_tick INTEGER,
    PRIMARY KEY (source_sha256, player_slot, ordinal),
    FOREIGN KEY (source_sha256, player_slot) REFERENCES players(source_sha256, player_slot)
);
CREATE INDEX IF NOT EXISTS idx_matches_match_id ON matches(match_id);
CREATE INDEX IF NOT EXISTS idx_item_events_item_key ON item_events(item_key);
"""


def _initialize_index(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if schema_version not in (0, 1):
        connection.close()
        raise ValueError(f"Unsupported data index schema version: {schema_version}")
    connection.executescript(SCHEMA_SQL)
    connection.execute("PRAGMA user_version = 1")
    return connection


def _write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def ingest_demo(source: Path, data_dir: Path, *, force: bool = False) -> dict[str, Any]:
    """Parse, normalize, and index one local replay; skip unchanged inputs."""
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"Replay file does not exist: {source}")
    source_sha = file_hash(source)
    database = data_dir / "index.sqlite"
    with closing(_initialize_index(database)) as index:
        existing = index.execute(
            "SELECT source_sha256, match_id, normalized_json, raw_json FROM matches "
            "WHERE source_sha256 = ?",
            (source_sha,),
        ).fetchone()
        cache_valid = False
        if existing and Path(existing[2]).is_file() and Path(existing[3]).is_file() and not force:
            try:
                cached = json.loads(Path(existing[2]).read_text(encoding="utf-8"))
                cache_valid = cached.get("schema_version") == ADAPTER_VERSION and cached.get(
                    "evidence_sha256"
                ) == file_hash(Path(existing[3]))
            except (ValueError, OSError, AttributeError):
                cache_valid = False
        if cache_valid:
            return {
                "status": "cached",
                "source_sha256": source_sha,
                "match_id": existing[1],
                "normalized_json": existing[2],
            }

    try:
        import gem
    except ImportError as error:
        raise ValueError("Gem is not installed; run pip install -e '.[replay]'") from error
    with prepared_demo(source, data_dir / ".tmp") as replay:
        replay_sha = file_hash(replay)
        match = gem.parse(replay)
    canonical, issues = canonicalize_match(match)
    for player in canonical["players"]:
        validated = normalize_match(
            canonical,
            player["player_slot"],
            source=source.name,
            fingerprint="sha256:" + replay_sha,
        )
        if any(flag.startswith("invalid_event:") for flag in validated.quality_flags):
            raise ValueError("Gem adapter produced an invalid purchase event")
    try:
        parser_version = version("gem-dota")
    except PackageNotFoundError:
        parser_version = "unknown"
    folder = data_dir / "matches" / source_sha
    folder.mkdir(parents=True, exist_ok=True)
    raw_path = folder / "raw-gem.json"
    normalized_path = folder / "normalized.json"
    manifest_path = folder / "manifest.json"
    raw = gem.to_json(match)
    # Fail before indexing if serialization is not valid JSON.
    json.loads(raw)
    canonical["evidence_source"] = raw_path.name
    canonical["evidence_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    temporary = raw_path.with_suffix(".json.tmp")
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(raw_path)
    _write_json(normalized_path, canonical)
    manifest = {
        "schema_version": "demo-import/1.0",
        "match_id": canonical["match_id"],
        "source_name": source.name,
        "source_sha256": source_sha,
        "demo_sha256": replay_sha,
        "raw_json_sha256": canonical["evidence_sha256"],
        "parser": "gem-dota",
        "parser_version": parser_version,
        "imported_at": datetime.now(UTC).isoformat(),
        "issues": issues,
        "raw_json": str(raw_path.resolve()),
        "normalized_json": str(normalized_path.resolve()),
    }
    _write_json(manifest_path, manifest)
    with closing(_initialize_index(database)) as index:
        with index:
            index.execute("DELETE FROM item_events WHERE source_sha256 = ?", (source_sha,))
            index.execute("DELETE FROM players WHERE source_sha256 = ?", (source_sha,))
            index.execute("DELETE FROM matches WHERE source_sha256 = ?", (source_sha,))
            index.execute(
                "INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_sha,
                    canonical["match_id"],
                    canonical["duration"],
                    canonical["game_mode"],
                    source.name,
                    parser_version,
                    str(raw_path.resolve()),
                    str(normalized_path.resolve()),
                    manifest["imported_at"],
                    len(issues),
                ),
            )
            for player in canonical["players"]:
                slot = player["player_slot"]
                index.execute(
                    "INSERT INTO players VALUES (?, ?, ?)", (source_sha, slot, player["hero_id"])
                )
                for ordinal, event in enumerate(player["purchase_log"]):
                    index.execute(
                        "INSERT INTO item_events VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            source_sha,
                            slot,
                            ordinal,
                            event["key"],
                            event["time"],
                            event["source_tick"],
                        ),
                    )
    return {
        "status": "imported",
        "source_sha256": source_sha,
        "demo_sha256": replay_sha,
        "match_id": canonical["match_id"],
        "normalized_json": str(normalized_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "players": len(canonical["players"]),
        "item_events": sum(len(p["purchase_log"]) for p in canonical["players"]),
        "issues": issues,
    }
