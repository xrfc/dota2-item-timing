"""Read preserved evidence and reproduce one event with existing project code.

Run with the project's .venv/bin/python. No binary replay parsing or training.
New results go to ignored learning/output by default.
Frozen lesson and source archives stay unchanged.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--evidence-root",
    type=Path,
    required=True,
    help="External saved evidence directory (ZIPs and receipts)",
)
parser.add_argument(
    "--output",
    type=Path,
    default=REPO / "learning/output/event-lineage/9031371970/trace-result.json",
)
args = parser.parse_args()
EVIDENCE = args.evidence_root.resolve()
sys.path.insert(0, str(REPO / "src"))
import gem  # noqa: E402

from dota_items.data.cleaning import clean_match  # noqa: E402
from dota_items.data.contracts import PreparationConfig  # noqa: E402
from dota_items.data.features import extract_samples  # noqa: E402
from dota_items.sources.gem_replay import canonicalize_match  # noqa: E402
from dota_items.workflow.validation import validate_match  # noqa: E402

MATCH = 9031371970
REF = "players[0].purchase_log[6]"
SAMPLE = f"{MATCH}:0:120"
checks = {}


def check(name, condition):
    checks[name] = bool(condition)
    if not condition:
        raise AssertionError(name)


def sha_file(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


receipt = json.loads((EVIDENCE / "verification-receipt.json").read_text(encoding="utf-8"))
receipt = next(r for r in receipt["matches"] if r["match_id"] == MATCH)
archive_hash = sha_file(EVIDENCE / receipt["replay"])
check("replay_archive_sha256", archive_hash == receipt["archive_sha256"])
with zipfile.ZipFile(EVIDENCE / "11382665563-original-replays-and-workspaces.zip") as z:
    raw_member = next(
        n for n in z.namelist() if f"workspaces/{MATCH}/" in n and n.endswith("/raw-gem.json")
    )
    raw_bytes = z.read(raw_member)
raw_hash = hashlib.sha256(raw_bytes).hexdigest()
check("raw_sha256", raw_hash == receipt["raw_gem_sha256"])
raw = json.loads(raw_bytes)
with zipfile.ZipFile(EVIDENCE / "11406303075-final-audit-and-samples.zip") as z:
    prefix = f"exports/{MATCH}/"
    saved = json.loads(z.read(prefix + "cleaned.json"))
    samples = {}
    for kind in ("features", "labels", "trace"):
        samples[kind] = next(
            json.loads(line)
            for line in z.read(prefix + kind + ".jsonl").splitlines()
            if json.loads(line)["sample_id"] == SAMPLE
        )
    report = next(r for r in json.loads(z.read("report.json"))["results"] if r["match_id"] == MATCH)
check("cleaned_source_sha256", saved["evidence_sha256"] == raw_hash)
check("match_identity", raw["match_id"] == saved["match_id"] == MATCH)
rp, sp = raw["players"][0], saved["players"][0]
event = rp["purchase_log"][6]
saved_event = next(e for e in sp["purchase_log"] if e["source_ref"] == REF)
check(
    "player_identity",
    rp["player_id"] == sp["player_slot"] == 0 and rp["hero_id"] == sp["hero_id"] == 106,
)
check(
    "event_target_identity", event["target_name"] == rp["hero_name"] == "npc_dota_hero_ember_spirit"
)
check("purchase_kind", event["log_type"] == "PURCHASE" and event["value_name"] == "item_bottle")
check("event_tick", event["tick"] == saved_event["source_tick"] == 9196)
check("event_time", event["game_time_s"] == saved_event["time"] == 122)

# Reuse the real adapter, cleaner and feature builder, not a parallel implementation.
parsed = gem.from_dict(raw)
clock_seconds = parsed.game_clock.game_seconds_at(event["tick"])
check("clock_mapping", clock_seconds == event["game_time_s"])
canonical, _ = canonicalize_match(parsed)
canonical_event = next(e for e in canonical["players"][0]["purchase_log"] if e["source_ref"] == REF)
config = PreparationConfig()
cleaned, quality = clean_match(canonical, config)
current_event = next(e for e in cleaned["players"][0]["purchase_log"] if e["source_ref"] == REF)
check("current_cleaned_event_equals_saved", current_event == saved_event)
rebuilt = extract_samples(cleaned, quality, config, slots=[0])
for kind, rows in zip(("features", "labels", "trace"), rebuilt, strict=True):
    check(
        f"current_{kind}_equals_saved",
        next(r for r in rows if r["sample_id"] == SAMPLE) == samples[kind],
    )
check(
    "purchase_is_label_not_feature",
    REF in samples["trace"]["label_refs"] and REF not in samples["trace"]["feature_refs"],
)
check(
    "future_window",
    samples["trace"]["cutoff_seconds"]
    < saved_event["time"]
    <= samples["trace"]["horizon_end_seconds"],
)
check(
    "label_other_not_no_purchase",
    samples["labels"]["item_action"] == "other"
    and samples["labels"]["item_mask"] is True
    and "bottle" not in config.candidate_items,
)
with tempfile.TemporaryDirectory(prefix="dota-event-lesson-") as tmp:
    folder = Path(tmp)
    (folder / "raw.json").write_bytes(raw_bytes)
    relocated = dict(saved, evidence_source="raw.json")
    (folder / "cleaned.json").write_text(json.dumps(relocated), encoding="utf-8")
    validation = validate_match(folder / "cleaned.json")
check("saved_match_identity_validator", True)

result = {
    "scope": (
        "Saved evidence chain and current adapter/cleaner/sample reproduction. "
        "Not binary replay parsing or game-client semantic verification. Training remains held."
    ),
    "code_commit": subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
    ).strip(),
    "match_id": MATCH,
    "replay_archive_sha256": archive_hash,
    "raw_member": raw_member,
    "raw_gem_sha256": raw_hash,
    "identity": {
        "player_id": rp["player_id"],
        "player_slot": sp["player_slot"],
        "hero_id": rp["hero_id"],
        "hero_name": rp["hero_name"],
    },
    "raw_event": event,
    "game_clock": raw["game_clock"],
    "clock_seconds_at_event_tick": clock_seconds,
    "canonical_event": canonical_event,
    "cleaned_event": saved_event,
    "preparation_config": config.model_dump(),
    "saved_sample": samples,
    "historical_mechanical_audit": {
        "pipeline_status": report["audit"]["pipeline_status"],
        "hold_reasons": report["audit"]["hold_reasons"],
        "decision_quality_supervision": report["audit"]["decision_quality_supervision"],
    },
    "checks": checks,
}
target = args.output
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "result": str(target),
            "raw_event": {
                k: event[k] for k in ("tick", "value_name", "game_time_s", "timestamp_s", "source")
            },
            "clock": raw["game_clock"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
