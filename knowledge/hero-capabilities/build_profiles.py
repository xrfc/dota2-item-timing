"""Build evidence-backed dossiers. Text matches are review candidates, not ratings."""

import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Explicit retrieval patterns, not a model that claims to understand all abilities.
# A match only places a skill in a review queue. Non-match NEVER proves absence.
DIMENSIONS = {
    "stun": ("眩晕", r"\bstun(?:s|ned|ning)?\b"),
    "root": ("缠绕／定身", r"\broot(?:s|ed|ing)?\b|\banchor(?:s|ed|ing)?\b"),
    "silence": ("沉默", r"\bsilenc(?:e|es|ed|ing)\b|prevents?[^.]*casting spells"),
    "mute": (
        "禁用物品",
        r"\bmut(?:e|ed|es|ing)\b|(?:cannot|unable to|prevents?)[^.]*us(?:e|ing) items",
    ),
    "disarm": ("缴械", r"\bdisarm(?:s|ed|ing)?\b|unable to attack"),
    "slow": ("减速", r"\bslow(?:s|ed|ing)?\b"),
    "forced_movement": (
        "强制位移",
        r"knock[^.]*back|push(?:es|ed)?[^.]*back|"
        r"pull(?:s|ed|ing)?[^.]*toward|teleports? the target",
    ),
    "area_restriction": ("区域限制", r"barrier|enemies (?:cannot|can't) pass|wall of"),
    "attack_interaction": (
        "攻击机制",
        r"\battack modifier|\bcritical|\bcleav(?:e|es|ing)\b|\bbonus attack damage",
    ),
    "area_effect": ("范围作用", r"\barea|\bradius|\bnearby|\ball enemies"),
    "damage_over_time": (
        "持续伤害",
        r"damage (?:over time|each second|per second)|damage each|damage every",
    ),
    "health_scaling": (
        "生命值相关伤害",
        r"percent[^.]*health|how much life[^.]*missing|missing health|max(?:imum)? hp",
    ),
    "mana_interaction": ("魔法值机制", r"\bmana\b"),
    "armor_interaction": ("护甲机制", r"\barmor\b"),
    "mobility": (
        "位移／机动",
        r"\bblink|\bleaps?\b|\bteleport|\bmovement speed|\bdash(?:es|ing)?\b|\brush(?:es|ing)?\b",
    ),
    "healing": ("治疗／恢复", r"\bheal(?:s|ing)?\b|\bhealth regen|restorative"),
    "shield": ("护盾／伤害吸收", r"\bshield|\bbarrier|\babsorb"),
    "dispel": ("驱散", r"\bdispel(?:s|led|ling)?\b"),
    "invisibility": ("隐身相关", r"\binvisib(?:le|ility)\b"),
    "vision": ("视野／侦测", r"\bvision\b|\breveal(?:s|ed|ing)?\b|true sight"),
    "summons": ("召唤物相关", r"\bsummon(?:s|ed|ing)?\b|\billusions?\b|forges? a spirit"),
    "building_interaction": ("建筑作用", r"\bbuildings?\b|\btowers?\b|\bstructures?\b"),
}
ROLE_ZH = {
    "Carry": "核心潜力",
    "Support": "辅助潜力",
    "Nuker": "爆发潜力",
    "Disabler": "控制潜力",
    "Jungler": "野区能力标签",
    "Durable": "承伤潜力",
    "Escape": "逃生潜力",
    "Pusher": "推进潜力",
    "Initiator": "先手潜力",
}


def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", value or "")).strip()


def load_hero(hero_id, language):
    return json.loads(
        (ROOT / "sources" / f"hero-{hero_id}-{language}.json").read_text(encoding="utf-8")
    )["result"]["data"]["heroes"][0]


def main():
    manifest = json.loads((ROOT / "source-manifest.json").read_text(encoding="utf-8"))
    if manifest["errors"] or len(manifest["records"]) != manifest["expected_detail_files"]:
        raise ValueError("Incomplete source snapshot")
    for record in manifest["records"] + manifest["catalog_files"]:
        if hashlib.sha256((ROOT / record["file"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Source fingerprint mismatch: {record['file']}")
    heroes = json.loads((ROOT / "sources/herolist-english.json").read_text(encoding="utf-8"))[
        "result"
    ]["data"]["heroes"]
    od = json.loads((ROOT / "sources/opendota-heroes.json").read_text(encoding="utf-8"))
    dossiers, coverage = [], []
    (ROOT / "heroes").mkdir(exist_ok=True)
    missing_desc, locale_missing, ability_count = [], [], 0
    for hero in heroes:
        hid = hero["id"]
        en, zh = load_hero(hid, "english"), load_hero(hid, "schinese")
        if en["id"] != zh["id"] or en["name"] != zh["name"]:
            raise ValueError("Locale hero identity conflict")
        od_hero = od.get(str(hid))
        od_agreement = od_hero is not None and od_hero["name"] == en["name"]
        if not od_agreement:
            raise ValueError(f"Catalog identity conflict for {hid}")
        skills, signals = [], []
        for collection in ("abilities", "facet_abilities"):
            en_rows, zh_rows = en.get(collection, []), zh.get(collection, [])
            # Unknown source structure cannot silently be ignored.
            if not isinstance(en_rows, list) or not isinstance(zh_rows, list):
                raise ValueError(f"Unexpected {collection} structure for {hid}")
            localized = {a["name"]: a for a in zh_rows}
            for index, ability in enumerate(en_rows):
                if not isinstance(ability, dict) or "name" not in ability:
                    raise ValueError("Unexpected skill schema")
                cn = localized.get(ability["name"])
                if cn is None:
                    locale_missing.append([hid, ability["name"]])
                    cn = {}
                ref = f"/result/data/heroes/0/{collection}/{index}"
                desc = plain(ability.get("desc_loc"))
                if not desc:
                    missing_desc.append([hid, ability["name"]])
                skill = {
                    "name": ability["name"],
                    "id": ability["id"],
                    "name_zh": plain(cn.get("name_loc")),
                    "name_en": plain(ability.get("name_loc")),
                    "description_zh": plain(cn.get("desc_loc")),
                    "description_en": desc,
                    "notes_zh": [plain(x) for x in cn.get("notes_loc", [])],
                    "notes_en": [plain(x) for x in ability.get("notes_loc", [])],
                    "source_collection": collection,
                    "source_pointer": ref,
                    "innate": ability.get("ability_is_innate"),
                    "granted_by_scepter": ability.get("ability_is_granted_by_scepter"),
                    "granted_by_shard": ability.get("ability_is_granted_by_shard"),
                    "upgrade_text": {
                        key: {"en": plain(ability.get(key)), "zh": plain(cn.get(key))}
                        for key in ("scepter_loc", "shard_loc")
                    },
                    "facet_text_en": ability.get("facets_loc", []),
                    "facet_text_zh": cn.get("facets_loc", []),
                    "cast_ranges": ability.get("cast_ranges"),
                    "cooldowns": ability.get("cooldowns"),
                    "mana_costs": ability.get("mana_costs"),
                    "cast_points": ability.get("cast_points"),
                    "channel_times": ability.get("channel_times"),
                    "special_values": ability.get("special_values"),
                    # Store opaque enums; do not guess behavior/immunity meanings.
                    "raw_mechanics": {
                        k: ability.get(k)
                        for k in (
                            "type",
                            "behavior",
                            "target_team",
                            "target_type",
                            "damage",
                            "immunity",
                            "dispellable",
                            "max_level",
                        )
                    },
                }
                skills.append(skill)
                for key, (label, pattern) in DIMENSIONS.items():
                    match = re.search(pattern, desc, flags=re.I)
                    if match:
                        signals.append(
                            {
                                "dimension": key,
                                "dimension_zh": label,
                                "ability": ability["name"],
                                "matched_text": match.group(0),
                                "evidence_description_en": desc,
                                "source_file": f"sources/hero-{hid}-english.json",
                                "source_pointer": ref + "/desc_loc",
                                "status": "text_signal_needs_review",
                                "availability": "conditional_not_currently_available",
                                "granted_by_scepter": skill["granted_by_scepter"],
                                "granted_by_shard": skill["granted_by_shard"],
                            }
                        )
        ability_count += len(skills)
        profile = {
            "hero_id": hid,
            "npc_name": en["name"],
            "name_zh": zh["name_loc"],
            "name_en": en["name_loc"],
            "learning_scope": manifest["learning_scope"],
            "source_patch": None,
            "target_patch": manifest["target_patch"],
            "patch_verified": False,
            "knowledge_status": "official_source_facts_with_unreviewed_interpretation",
            "published_role_labels": od_hero.get("roles", []),
            "role_source": (
                "OpenDota dotaconstants bf193a550f778dec35debf4d71d05a86bebcc418; "
                "descriptive role labels, not matchup ratings"
            ),
            "official_role_levels_raw": en.get("role_levels"),
            "hero_summary_zh": plain(zh.get("hype_loc")),
            "hero_summary_en": plain(en.get("hype_loc")),
            "base_stats": {
                k: en.get(k)
                for k in (
                    "attack_range",
                    "damage_min",
                    "damage_max",
                    "attack_rate",
                    "movement_speed",
                    "armor",
                    "magic_resistance",
                    "sight_range_day",
                    "sight_range_night",
                )
            },
            "abilities": skills,
            "talents_raw": en.get("talents", []),
            "facets_raw": en.get("facets", []),
            "capability_review_signals": signals,
            "source_files": [
                f"sources/hero-{hid}-english.json",
                f"sources/hero-{hid}-schinese.json",
            ],
            "open_questions": [
                "Exact patch correspondence",
                "Interpretation of mechanics enums",
                "Availability by level/facet/upgrade",
                "Reliability and prerequisites of each effect",
                "Matchup and equipment recommendations require separate review",
            ],
        }
        dossiers.append(profile)
        (ROOT / "heroes" / f"{hid}.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        lines = [
            f"# {zh['name_loc']} / {en['name_loc']}（{hid}）",
            "",
            "**资料状态：官方当前快照；版本未确认。能力线索待核验，不是评分或出装结论。**",
            "",
            "## 英雄简介（官方）",
            "",
            profile["hero_summary_zh"],
            "",
            "## 已发布角色标签（OpenDota）",
            "",
            "、".join(ROLE_ZH.get(x, x) for x in profile["published_role_labels"]),
            "",
            "角色标签不确定实际分路，也不证明阵容强度。",
            "",
            "## 技能逐项解构",
            "",
        ]
        for s in skills:
            lines += [
                f"### {s['name_zh'] or s['name_en']} / {s['name']}",
                "",
                s["description_zh"] or s["description_en"],
                "",
                f"来源：[中文原文](../sources/hero-{hid}-schinese.json)；"
                f"[英文原文](../sources/hero-{hid}-english.json) `{s['source_pointer']}`。",
                "",
                f"先天标记：{s['innate']}；神杖授予：{s['granted_by_scepter']}；魔晶授予：{s['granted_by_shard']}。",
                "",
                f"冷却数组：`{s['cooldowns']}`；魔耗数组：`{s['mana_costs']}`；施法距离数组：`{s['cast_ranges']}`。",
                "",
                "这些数组保留源值，不自动认定当前等级，也不凭长度推断有效等级。",
                "",
            ]
            if s["notes_zh"]:
                lines += ["官方注意事项：", ""] + ["- " + x for x in s["notes_zh"]] + [""]
            for upgrade, title in [("scepter_loc", "神杖条件效果"), ("shard_loc", "魔晶条件效果")]:
                text = s["upgrade_text"][upgrade]["zh"] or s["upgrade_text"][upgrade]["en"]
                if text:
                    lines += [f"{title}：{text}", ""]
            facets = [plain(t) for t in s["facet_text_zh"] if plain(t)]
            if facets:
                lines += (
                    ["命石说明残留／条件文本（是否现行未确认）：", ""]
                    + ["- " + t for t in facets]
                    + [""]
                )
        grouped = Counter(s["dimension_zh"] for s in signals)
        lines += [
            "## 待核验的能力检索线索",
            "",
            "、".join(grouped) or "未检索到线索；不能据此判断该英雄没有能力。",
            "",
            "以上由描述中的词语检索产生，可能包含限制、否定或对敌方的效果；不能直接用于反制、评分或推荐。没有命中不等于没有该能力。",
            "",
            f"完整数值、英文限制、天赋原文和证据见 [{hid}.json]({hid}.json)。",
        ]
        markdown = "\n".join(line.rstrip() for line in "\n".join(lines).splitlines()) + "\n"
        (ROOT / "heroes" / f"{hid}.md").write_text(markdown, encoding="utf-8")
        coverage.append(
            {
                "hero_id": hid,
                "name_zh": zh["name_loc"],
                "abilities": len(skills),
                "text_signals": len(signals),
                "catalog_identity_agreement": od_agreement,
            }
        )
    registry = {
        "schema": "draft-hero-capability-registry/1",
        "learning_scope": manifest["learning_scope"],
        "historical_adaptation": "deferred",
        "target_patch": manifest["target_patch"],
        "source_patch": None,
        "patch_verified": False,
        "dimensions": {k: v[0] for k, v in DIMENSIONS.items()},
        "heroes": dossiers,
    }
    (ROOT / "hero-registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checks = {
        "schema": "hero-capability-coverage/1",
        "heroes_expected": len(heroes),
        "heroes_built": len(dossiers),
        "source_detail_files": len(manifest["records"]),
        "abilities_built": ability_count,
        "catalog_identity_agreements": sum(x["catalog_identity_agreement"] for x in coverage),
        "missing_english_descriptions": missing_desc,
        "missing_chinese_ability_links": locale_missing,
        "mechanism_assessments_approved": 0,
        "patch_verified": False,
        "heroes": coverage,
    }
    (ROOT / "coverage.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "HEROES.md").write_text(
        "# 全英雄档案索引\n\n官方当前快照；版本对应与机制解释待核验。\n\n"
        "| ID | 英雄 | 技能条目 | 档案 |\n|---|---|---|---|\n"
        + "\n".join(
            f"| {h['hero_id']} | {h['name_zh']} / {h['name_en']} | "
            f"{len(h['abilities'])} | [查看](heroes/{h['hero_id']}.md) |"
            for h in dossiers
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps({k: v for k, v in checks.items() if k != "heroes"}, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
