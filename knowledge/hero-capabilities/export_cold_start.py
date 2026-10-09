"""Export source-extraction candidates; no inferred mechanics or decision labels."""

import hashlib
import json
from pathlib import Path

from build_profiles import plain

ROOT = Path(__file__).resolve().parent


def build_candidates(root=ROOT):
    manifest = json.loads((root / "source-manifest.json").read_text(encoding="utf-8"))
    if manifest["errors"] or len(manifest["records"]) != manifest["expected_detail_files"]:
        raise ValueError("Incomplete source manifest")
    records = manifest["records"] + manifest["catalog_files"]
    for record in records:
        if hashlib.sha256((root / record["file"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Source fingerprint mismatch: {record['file']}")
    snapshot_id = hashlib.sha256(
        json.dumps(
            sorted((r["file"], r["sha256"]) for r in records), separators=(",", ":")
        ).encode()
    ).hexdigest()
    source_map = {(r["hero_id"], r["language"]): r for r in manifest["records"]}
    heroes = json.loads((root / "sources/herolist-english.json").read_text(encoding="utf-8"))[
        "result"
    ]["data"]["heroes"]
    candidates = []
    for hero in heroes:
        record = source_map[(hero["id"], "schinese")]
        localized = json.loads((root / record["file"]).read_text(encoding="utf-8"))["result"][
            "data"
        ]["heroes"][0]
        if localized["id"] != hero["id"] or localized["name"] != hero["name"]:
            raise ValueError("Hero identity mismatch")
        for collection in ("abilities", "facet_abilities"):
            for ordinal, ability in enumerate(localized.get(collection, [])):
                if not plain(ability.get("desc_loc")):
                    raise ValueError("Missing localized source description")
                pointer = f"/result/data/heroes/0/{collection}/{ordinal}"
                answer = {
                    "description": plain(ability["desc_loc"]),
                    "notes": [plain(x) for x in ability.get("notes_loc", [])],
                    "scepter_description": plain(ability.get("scepter_loc")),
                    "shard_description": plain(ability.get("shard_loc")),
                    "granted_by_scepter": ability.get("ability_is_granted_by_scepter"),
                    "granted_by_shard": ability.get("ability_is_granted_by_shard"),
                }
                candidates.append(
                    {
                        "sample_id": f"{snapshot_id}:{hero['id']}:{collection}:{ordinal}",
                        "task": "official_ability_source_extraction",
                        "status": "candidate_not_training_admitted",
                        "training_allowed": False,
                        "group_id": f"hero:{hero['id']}",
                        "hero_id": hero["id"],
                        "ability_name": ability["name"],
                        "learning_scope": "current_official_snapshot",
                        "source_patch": None,
                        "snapshot_id": snapshot_id,
                        "source": {
                            "file": record["file"],
                            "url": record["url"],
                            "sha256": record["sha256"],
                            "pointer": pointer,
                        },
                        "instruction": (
                            f"从所附官网快照提取{localized['name_loc']}技能"
                            f"“{plain(ability['name_loc'])}”的说明、注意事项和升级条件。"
                            "只摘录来源，不补充克制、评分、装备建议；保留未解析参数。"
                        ),
                        "input": answer,
                        "output": answer,
                    }
                )
    return candidates


def main():
    candidates = build_candidates()
    output = ROOT / "cold-start"
    output.mkdir(exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in candidates)
    (output / "candidates.jsonl").write_text(payload, encoding="utf-8", newline="\n")
    manifest = {
        "schema": "hero-knowledge-cold-start/1",
        "task": "official_ability_source_extraction",
        "status": "candidate_not_training_admitted",
        "training_allowed": False,
        "snapshot_id": candidates[0]["snapshot_id"],
        "samples": len(candidates),
        "hero_groups": len({r["group_id"] for r in candidates}),
        "file": "candidates.jsonl",
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "split_policy": (
            "Group all locales, upgrades and paraphrases of a hero together; "
            "no split is created or admitted by this export."
        ),
        "limitations": [
            "Source extraction pairs, not independent factual recall or reasoning supervision",
            "No equipment choice, counter claim, matchup winner or decision-quality label",
            "No unreviewed keyword signals used in outputs",
            "Exact patch, semantic review and third-party reuse terms still require assessment",
            "Not connected to replay training admission or any model trainer",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: manifest[k] for k in ("samples", "hero_groups", "training_allowed")}))


if __name__ == "__main__":
    main()
