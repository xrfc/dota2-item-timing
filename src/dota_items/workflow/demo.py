"""Offline infrastructure smoke data; no model and no genuine Dota match."""

from ..storage import write_json
from .contracts import Labels
from .datasets import build_dataset
from .reviews import review
from .workspace import Workspace


def demo(workspace: Workspace) -> dict:
    workspace.init()
    for index in range(6):
        match_id = 1000000100 + index
        path = workspace.root / "inbox" / "synthetic" / f"{match_id}.json"
        write_json(
            path,
            {
                "_fixture": "Synthetic pipeline fixture. Not expert play or training evidence.",
                "schema_version": "gem-adapter/2.0",
                "match_id": match_id,
                "duration": 300,
                "patch": None,
                "game_mode": 22,
                "players": [
                    {
                        "player_slot": 0,
                        "hero_id": 44,
                        "purchase_log": [
                            {"time": 0, "key": "tango"},
                            {"time": 180, "key": "boots"},
                        ],
                        "position_log": [
                            {"time": t, "x": -5000 + 10 * t + index, "y": -5000 + 5 * t}
                            for t in range(0, 301, 10)
                        ],
                        "economy_log": [
                            {
                                "time": t,
                                "gold": 500 + t,
                                "net_worth": 600 + 3 * t,
                                "last_hits": t // 10,
                                "denies": 0,
                                "xp_progress": t % 100,
                            }
                            for t in range(0, 301, 10)
                        ],
                    }
                ],
            },
        )
        workspace.import_json(path)
        workspace.annotate(
            match_id,
            Labels(
                tier="synthetic",
                patch="synthetic",
                role=1,
                player_slots=[0],
                label_source="Built-in workflow fixture; no expert demonstrations",
            ),
        )
    dataset = build_dataset(
        workspace, patch="synthetic", role=1, require_spatial=True, allow_synthetic=True
    )
    facts = review(workspace, 1000000100, 0)
    return {
        "mode": "synthetic infrastructure smoke test",
        "dataset": dataset,
        "report": facts["report"],
        "doctor": workspace.doctor(),
        "note": "No model was trained or invoked.",
    }
