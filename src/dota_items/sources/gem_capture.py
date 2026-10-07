"""Gem 0.10 orchestration with retained state samples; no replay protocol implementation."""

from importlib.metadata import version

CAPTURE_VERSION = "gem-state-capture/2"


def snapshot_evidence(extractor, snapshot, empty_handle):
    """Read presence from the same live entity, rather than accepting Gem's zero defaults."""
    hero = extractor._canonical_hero_entity(snapshot.player_id)
    if hero is None:
        return None
    fields = {
        "hp": "m_iHealth",
        "max_hp": "m_iMaxHealth",
        "mana": "m_flMana",
        "max_mana": "m_flMaxMana",
        "life_state": "m_lifeState",
    }
    result = {
        "tick": snapshot.tick,
        "player_id": snapshot.player_id,
        "entity_index": hero.get_index(),
        "entity_serial": hero.get_serial(),
        "level": snapshot.level if snapshot.level > 0 else None,
        "ability_levels": dict(snapshot.ability_levels),
        "items": {str(slot): item for slot, item in snapshot.items.items()},
        "inventory_slots": list(range(17)),
    }
    for name, field in fields.items():
        getter = hero.get_float32 if name in ("mana", "max_mana") else hero.get_int32
        result[name] = getter(field)
    # Slot names are resolved by Gem. An absent handle or unresolved occupied slot
    # makes inventory incomplete; an explicitly empty slot remains a known empty slot.
    unknown = []
    handles = {}
    for slot in range(17):
        handle = hero.get_uint32(f"m_hItems.{slot:04d}")
        handles[str(slot)] = handle
        if handle is None or (handle != empty_handle and str(slot) not in result["items"]):
            unknown.append(slot)
    result["inventory_handles"] = handles
    result["inventory_empty_handle"] = empty_handle
    result["inventory_unknown_slots"] = unknown
    result["inventory_complete"] = not unknown
    return result


def parse_with_state(path):
    """Reuse Gem extractors/assembly and retain state omitted by its default JSON.

    This small wiring layer follows gem.api.parse at v0.10.0. The subclass and
    assembler use version-specific APIs deliberately; pin and regression-test them.
    No global monkey patching, duplicate hero/item tables, or protocol decoding.
    """
    if version("gem-dota") != "0.10.0":
        raise ValueError("State capture requires the verified gem-dota==0.10.0")
    from gem.combat.aggregator import _CombatAggregator
    from gem.extractors.courier import CourierExtractor
    from gem.extractors.draft import DraftExtractor
    from gem.extractors.intervals import IntervalExtractor
    from gem.extractors.objectives import ObjectivesExtractor
    from gem.extractors.players import _NULL_HANDLE, PlayerExtractor
    from gem.extractors.smoke_vision import SmokeExtractor, VisionModifierExtractor
    from gem.extractors.visibility import VisibilityExtractor
    from gem.extractors.wards import WardsExtractor
    from gem.parser import ReplayParser
    from gem.results.assembly import build_parsed_match

    class StatePlayerExtractor(PlayerExtractor):
        def __init__(self):
            super().__init__()
            self.coach_states = []

        def _sample(self, tick, *, minute=False):
            start = len(self.snapshots)
            super()._sample(tick, minute=minute)
            for snapshot in self.snapshots[start:]:
                row = snapshot_evidence(self, snapshot, _NULL_HANDLE)
                if row is not None:
                    self.coach_states.append(row)

    parser = ReplayParser(path)
    players = StatePlayerExtractor()
    visibility = VisibilityExtractor(players)
    intervals = IntervalExtractor()
    objectives = ObjectivesExtractor()
    wards = WardsExtractor()
    couriers = CourierExtractor()
    draft = DraftExtractor()
    smoke = SmokeExtractor(players)
    modifiers = VisionModifierExtractor(players)
    for extractor in (players, visibility, intervals, objectives, wards, couriers, draft):
        extractor.attach(parser)
    combat = _CombatAggregator(players)
    entries, chat, neutral = [], [], []
    parser.on_combat_log_entry(combat.on_entry)
    parser.on_combat_log_entry(entries.append)
    parser.on_chat_message(chat.append)
    parser.on_neutral_item_found(neutral.append)
    smoke.attach(parser)
    modifiers.attach(parser)
    parser.parse()
    draft.finalize()
    wards.finalize()
    match = build_parsed_match(
        parser=parser,
        player_ext=players,
        obj_ext=objectives,
        ward_ext=wards,
        courier_ext=couriers,
        draft_ext=draft,
        combat_agg=combat,
        all_entries=entries,
        chat_entries=chat,
        smoke_events=smoke.finalize(),
        vision_modifier_events=modifiers.finalize(),
        vision_modifier_pairing_issues=modifiers.pairing_issues,
        neutral_item_finds=neutral,
        interval_ext=intervals,
        hero_visibility_events=visibility.events,
        entity_visibility_events=visibility.entity_events,
    )
    return match, players.coach_states
