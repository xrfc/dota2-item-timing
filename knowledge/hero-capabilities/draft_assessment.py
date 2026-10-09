"""Evidence inventory for a completed draft; never emits win odds or item recommendations."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Checked against the saved official descriptions. Still not patch-certified.
# Deliberately narrow: no inferred reliability ratings or invented counter relations.
SOURCE_CHECKED = [
    (
        106,
        "ember_spirit_searing_chains",
        "root",
        "近身缠绕与持续伤害",
        [
            "需要技能可用并满足目标选择条件；不是眩晕",
            "官方说明：随机选择附近目标，不能作用于减益免疫或隐身单位",
        ],
        "base",
    ),
    (
        18,
        "sven_storm_bolt",
        "stun",
        "目标周围的范围眩晕",
        ["需要技能可用、施放并命中；不能仅凭选人假定成功先手"],
        "base",
    ),
    (
        18,
        "sven_great_cleave",
        "attack_area_damage",
        "攻击造成分裂伤害",
        ["依赖攻击发生及目标位置；不直接推出清线速度或幻象克制程度"],
        "base",
    ),
    (
        87,
        "disruptor_glimpse",
        "forced_reposition",
        "将目标英雄送回此前位置",
        ["依赖历史位置、目标资格和技能可用性；不等于任意时刻都能抓住目标"],
        "base",
    ),
    (
        87,
        "disruptor_static_storm",
        "silence",
        "区域沉默与逐渐增强的伤害",
        ["目标需要受到区域作用；基础效果不能自动写成禁用物品"],
        "base",
    ),
    (
        87,
        "disruptor_static_storm",
        "mute",
        "静态风暴的神杖升级具有禁用物品效果",
        ["必须确认已拥有相应升级；不能计入选人阶段已具备的基础能力"],
        "scepter",
    ),
    (
        69,
        "doom_bringer_doom",
        "spell_and_healing_denial",
        "限制目标施法和接受治疗，并施加驱散与持续伤害",
        ["需要目标受到末日作用；本条来源不支持自动追加禁用物品结论"],
        "base",
    ),
    (
        74,
        "invoker_deafening_blast",
        "disarm_and_knockback",
        "冲击波具有击退和禁止攻击效果",
        ["依赖技能可用、命中及元素等级；不能认为选到祈求者即拥有全部满级技能"],
        "base",
    ),
    (
        9,
        "mirana_arrow",
        "conditional_stun",
        "箭矢命中首个目标造成眩晕，时长与飞行距离相关",
        ["必须命中，可能先碰到其他单位；不能计作无条件稳定控制"],
        "base",
    ),
    (
        9,
        "mirana_invis",
        "team_invisibility",
        "给予己方英雄隐身",
        ["隐身不等于无敌或不可侦测；不能据此保证脱离战斗"],
        "base",
    ),
    (
        36,
        "necrolyte_death_pulse",
        "ally_healing",
        "附近敌方受伤害、友方受治疗",
        ["受作用范围与技能可用性限制；不能直接推断足以抵消敌方伤害"],
        "base",
    ),
    (
        36,
        "necrolyte_ghost_shroud",
        "defense_tradeoff",
        "无法攻击或被攻击，但受到的魔法伤害增加",
        ["是附带代价的防护机制；不是对所有伤害更耐打"],
        "base",
    ),
    (
        145,
        "kez_switch_weapons",
        "weapon_mode_dependency",
        "切换武器改变攻击特性和技能，并有对应技能冷却关系",
        ["实际模式、冷却与升级必须另外确认；不能把所有技能当作同时可用"],
        "base",
    ),
    (
        123,
        "hoodwink_bushwhack",
        "tree_conditional_stun",
        "靠近树木的目标受到眩晕和拖拽",
        ["依赖树木；树被摧毁会解除眩晕；官方说明不能命中隐身单位"],
        "base",
    ),
    (
        107,
        "earth_spirit_geomagnetic_grip",
        "ally_reposition_and_silence",
        "牵引残岩或友方单位，路径敌人受到沉默和伤害",
        ["需要有效目标和路径；官方说明时间结界、决斗、黑洞中的目标不适用"],
        "base",
    ),
]


def make_reviews(registry):
    by_id = {h["hero_id"]: h for h in registry["heroes"]}
    reviews = []
    for hid, skill, dim, claim, conditions, upgrade in SOURCE_CHECKED:
        hero = by_id[hid]
        ability = next(a for a in hero["abilities"] if a["name"] == skill)
        if upgrade == "scepter":
            en = ability["upgrade_text"]["scepter_loc"]["en"]
            zh = ability["upgrade_text"]["scepter_loc"]["zh"]
            pointer = ability["source_pointer"] + "/scepter_loc"
        else:
            en, zh = ability["description_en"], ability["description_zh"]
            pointer = ability["source_pointer"] + "/desc_loc"
        if not en or not zh:
            raise ValueError(f"Missing evidence for {skill}")
        reviews.append(
            {
                "hero_id": hid,
                "hero_name": hero["name_zh"],
                "ability": skill,
                "dimension": dim,
                "claim_zh": claim,
                "conditions": conditions,
                "requires_upgrade": upgrade,
                "status": "agent_source_checked_patch_unverified_user_review_pending",
                "evidence_zh": zh,
                "evidence_en": en,
                "notes_zh": ability["notes_zh"],
                "source_file": f"sources/hero-{hid}-schinese.json",
                "source_pointer": pointer,
            }
        )
    return reviews


def assess(registry, radiant, dire, target_patch, reviews):
    if len(radiant) != 5 or len(dire) != 5:
        raise ValueError("A complete draft requires five heroes per side")
    picks = radiant + dire
    if len(set(picks)) != 10:
        raise ValueError("Duplicate hero selections are invalid")
    by_id = {h["hero_id"]: h for h in registry["heroes"]}
    if any(type(hid) is not int or hid not in by_id for hid in picks):
        raise ValueError("Unknown hero ID")
    patch_admitted = bool(
        target_patch and registry["patch_verified"] and registry["source_patch"] == target_patch
    )
    result = {
        "schema": "draft-evidence-assessment/1",
        "mode": "draft_potential_not_runtime_strength",
        "learning_scope": registry["learning_scope"],
        "current_snapshot_learning": target_patch is None,
        "target_patch": target_patch,
        "source_patch": registry["source_patch"],
        "patch_admitted": patch_admitted,
        "decision_recommendation_allowed": False,
        "global_limitations": [
            "No win probability or total strength score",
            "No actual ability levels, chosen facets, items, cooldowns, "
            "positions or economy supplied",
            "Non-match in text retrieval is unknown, not absence",
            "Source-checked claims are patch-unverified and awaiting user review",
            "No automatic synergy or counter relation inferred",
        ],
        "sides": {},
    }
    for side, ids in [("radiant", radiant), ("dire", dire)]:
        selected = [by_id[hid] for hid in ids]
        claims = [r for r in reviews if r["hero_id"] in ids]
        result["sides"][side] = {
            "heroes": [
                {
                    "hero_id": h["hero_id"],
                    "name": h["name_zh"],
                    "published_role_labels": h["published_role_labels"],
                    "dossier": f"heroes/{h['hero_id']}.md",
                }
                for h in selected
            ],
            "base_source_checked_potential": [r for r in claims if r["requires_upgrade"] == "base"],
            "upgrade_potential_not_base": [r for r in claims if r["requires_upgrade"] != "base"],
            "unreviewed_text_signals": [
                dict(s, hero_id=h["hero_id"], hero_name=h["name_zh"])
                for h in selected
                for s in h["capability_review_signals"]
            ],
            "unknown_dimensions": [
                "damage sufficiency",
                "control reliability",
                "waveclear speed",
                "tower pressure strength",
                "actual role assignment",
                "synergy effectiveness",
                "equipment counter needs",
            ],
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--radiant", default="106,18,87,69,74")
    parser.add_argument("--dire", default="9,36,145,123,107")
    parser.add_argument(
        "--patch",
        default=None,
        help="Historical patch target; omit to study current official snapshot",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "draft-example.json")
    args = parser.parse_args()
    registry = json.loads((ROOT / "hero-registry.json").read_text(encoding="utf-8"))
    reviews = make_reviews(registry)
    (ROOT / "source-checked-examples.json").write_text(
        json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result = assess(
        registry,
        [int(x) for x in args.radiant.split(",")],
        [int(x) for x in args.dire.split(",")],
        args.patch,
        reviews,
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "source_checked_mechanisms": len(reviews),
                "patch_admitted": result["patch_admitted"],
                "recommendation_allowed": result["decision_recommendation_allowed"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
