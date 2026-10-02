"""Render traceable model outputs, or an ordinary facts report before a model exists."""

import uuid
from html import escape
from pathlib import Path
from typing import Any

from ..analysis import analyze
from ..normalize import load_timeline
from ..report import format_time, render_html
from .contracts import Predictions
from .jobs import load_model, run_program
from .storage import file_hash, now, read_json, write_json
from .validation import resolve_ref
from .workspace import Workspace


def validate_predictions(predictions: Predictions, raw: dict, slot: int, model_id: str) -> None:
    if (predictions.match_id, predictions.player_slot, predictions.model_id) != (
        raw["match_id"],
        slot,
        model_id,
    ):
        raise ValueError("Prediction match, player, or model identity mismatch")
    index = next(i for i, player in enumerate(raw["players"]) if player["player_slot"] == slot)
    allowed = tuple(
        f"players[{index}].{channel}["
        for channel in (
            "purchase_log",
            "position_log",
            "economy_log",
        )
    )
    for decision in predictions.decisions:
        if decision.time_seconds > raw["duration"]:
            raise ValueError("Prediction time is outside the match")
        for reference in decision.evidence_refs:
            if not reference.startswith(allowed):
                raise ValueError(
                    "Evidence must reference the selected player's observed time series"
                )
            value = resolve_ref(raw, reference)
            if not isinstance(value, dict) or "time" not in value:
                raise ValueError("Evidence must reference a whole timestamped observation")
            if value["time"] > decision.time_seconds:
                raise ValueError("Future evidence cannot explain a past decision")


def prediction_html(predictions: Predictions) -> str:
    cards = []
    for event in sorted(predictions.decisions, key=lambda item: item.time_seconds):
        options = "".join(
            f"<li>{escape(option.label)} — 模型分数 {option.score:.3f}</li>"
            for option in sorted(event.alternatives, key=lambda item: item.score, reverse=True)
        )
        evidence = "<br>".join(escape(ref) for ref in event.evidence_refs)
        cards.append(
            f"<article><h3>{format_time(event.time_seconds)} · "
            f"{'出装' if event.task == 'item' else '路线'}</h3>"
            f"<p>实际选择：{escape(event.observed_action or '未提供')}</p><ul>{options}</ul>"
            f"<p>{escape(event.note)}</p><details><summary>决策时刻证据</summary>"
            f"<code>{evidence}</code></details></article>"
        )
    limits = "".join(f"<li>{escape(item)}</li>" for item in predictions.limitations)
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DOTA2 教练复盘</title>
<style>body{{background:#111923;color:#e7eef6;font:16px/1.7 system-ui;margin:0}}
main{{max-width:960px;margin:40px auto;padding:0 24px}}article{{background:#1c2a39;
padding:20px;margin:16px 0;border-radius:12px}}a{{color:#7de0bd}}code{{overflow-wrap:anywhere}}
.notice{{border-left:3px solid #7de0bd;padding:12px}}</style><main><h1>DOTA2 教练复盘</h1>
<p>比赛 {predictions.match_id} · 槽位 {predictions.player_slot}</p>
<p class="notice">模型分数表示模型对候选决策的偏好。偏离参考选手的选择不等于犯错，
分数也不是获胜概率；请结合当时视野、资源、队伍计划和模型评估结果复核。</p>
<p><a href="facts.html">查看购买事实与数据质量</a> · <a href="predictions.json">预测 JSON</a></p>
{"".join(cards) or "<p>模型未返回可展示的决策。</p>"}
<h2>模型说明</h2><ul>{limits}</ul><p>模型 ID：<code>{escape(predictions.model_id)}</code></p>
</main></html>"""


def review(
    workspace: Workspace,
    match_id: int,
    slot: int,
    *,
    model_id: str | None = None,
    predictor: Path | None = None,
    timeout: float = 3600,
) -> dict[str, Any]:
    record, match_dir = workspace.record(match_id)
    normalized = match_dir / "normalized.json"
    timeline = load_timeline(normalized, slot)
    raw = read_json(normalized)
    if bool(model_id) != bool(predictor):
        raise ValueError("Provide both --model and --predictor, or neither for a facts report")
    registry = model_dir = None
    if model_id:
        registry, model_dir = load_model(workspace, model_id)
        dataset, _ = workspace.dataset(registry["dataset_id"])
        filters = dataset["filters"]
        labels = record["labels"]
        if not labels or labels["patch"] != filters["patch"] or labels["role"] != filters["role"]:
            raise ValueError("Annotate this match with the model's patch and role before review")
        if slot not in labels["player_slots"]:
            raise ValueError("Requested player is not included in this match's role annotation")
        if filters["hero_id"] and filters["hero_id"] != timeline.hero_id:
            raise ValueError("Hero is outside the model's dataset scope")
        if record["synthetic"] != filters["synthetic_only"]:
            raise ValueError("Synthetic model/data cannot be used as a real-match review")
    review_id = "review-" + uuid.uuid4().hex[:16]
    folder = workspace.root / "reviews" / review_id
    folder.mkdir()
    state = {
        "schema_version": "coach-review/1",
        "review_id": review_id,
        "match_id": match_id,
        "player_slot": slot,
        "model_id": model_id,
        "bundle_id": record["bundle_id"],
        "status": "running",
        "started_at": now(),
        "mode": "model" if model_id else "facts",
    }
    write_json(folder / "review.json", state)
    try:
        result = analyze(timeline, workspace.config().candidate_items)
        write_json(folder / "facts.json", result.model_dump())
        facts = render_html(result)
        (folder / "facts.html").write_text(facts, encoding="utf-8")
        if model_id:
            state["predictor_sha256"] = file_hash(predictor)
            state["command"] = run_program(
                predictor,
                [
                    "--model",
                    str(model_dir),
                    "--match",
                    str(normalized),
                    "--player-slot",
                    str(slot),
                    "--output",
                    str(folder / "predictions.json"),
                ],
                folder,
                timeout,
            )
            predictions = Predictions.model_validate(read_json(folder / "predictions.json"))
            validate_predictions(predictions, raw, slot, model_id)
            if any(event.task not in registry["model"]["tasks"] for event in predictions.decisions):
                raise ValueError("Prediction task is not declared by the model")
            if match_id in {row["match_id"] for row in dataset["matches"]}:
                predictions.limitations.append("该比赛已出现在模型数据集中，不属于独立的泛化验证。")
            workspace.record(match_id)
            load_model(workspace, model_id)
            write_json(folder / "predictions.json", predictions.model_dump())
            html = prediction_html(predictions)
        else:
            html = facts
        (folder / "report.html").write_text(html, encoding="utf-8")
        state.update(status="succeeded", report=str(folder / "report.html"))
    except BaseException as error:
        state.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            error=str(error),
            finished_at=now(),
        )
        write_json(folder / "review.json", state)
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ValueError(f"Review {review_id} failed: {error}") from error
    state["finished_at"] = now()
    write_json(folder / "review.json", state)
    return state
