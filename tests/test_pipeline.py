import json
from pathlib import Path

import pytest

from dota_items.analysis import analyze
from dota_items.cli import main
from dota_items.normalize import load_timeline, normalize_match
from dota_items.report import format_time, render_html

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "match.synthetic.json"


def raw_match():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def normalized(raw, slot=0):
    return normalize_match(raw, slot, source="test", fingerprint="sha256:test")


def test_first_record_is_earliest_without_losing_duplicate_events():
    raw = raw_match()
    raw["players"][0]["purchase_log"].reverse()
    result = analyze(normalized(raw), ["tpscroll"])
    assert result.first_records[0].time_seconds == 1500
    assert len([e for e in result.timeline.events if e.item_key == "tpscroll"]) == 2


def test_pregame_times_and_unknown_keys_are_preserved():
    raw = raw_match()
    raw["players"][0]["purchase_log"].append({"key": "future_item", "time": 100})
    timeline = normalized(raw)
    assert timeline.events[0].time_seconds == -30
    assert "future_item" in [event.item_key for event in timeline.events]
    assert format_time(-30) == "−00:30"


def test_missing_log_is_not_no_purchase():
    result = analyze(normalized(raw_match(), 128), ["blink"])
    assert result.timeline.purchase_log_status == "missing"
    assert result.timeline.quality_flags
    assert result.first_records == []


@pytest.mark.parametrize("time", [True, "120", float("nan"), float("inf"), 2101])
def test_bad_times_are_flagged_and_excluded(time):
    raw = raw_match()
    raw["players"][0]["purchase_log"] = [{"key": "blink", "time": time}]
    timeline = normalized(raw)
    assert timeline.events == []
    assert any(flag.startswith("invalid_event:") for flag in timeline.quality_flags)


def test_wrong_player_slot_is_rejected():
    with pytest.raises(ValueError, match="Expected one player"):
        normalized(raw_match(), 7)


def test_report_escapes_external_labels():
    raw = raw_match()
    raw["players"][0]["purchase_log"] = [{"key": "<script>alert(1)</script>", "time": 0}]
    result = analyze(normalized(raw), ["<script>alert(1)</script>"])
    html = render_html(result)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_fixture_pipeline_and_output_provenance(tmp_path):
    assert (
        main(
            [
                "report",
                str(FIXTURE),
                "--player-slot",
                "0",
                "--config",
                str(ROOT / "configs" / "analysis.json"),
                "--output",
                str(tmp_path),
            ]
        )
        == 0
    )
    result = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert result["timeline"]["source_fingerprint"].startswith("sha256:")
    assert [e["time_seconds"] for e in result["first_records"]] == [420, 1100, 1390]
    assert "日志首次记录" in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_invalid_json_fails_cleanly(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")
    assert (
        main(
            [
                "report",
                str(bad),
                "--player-slot",
                "0",
                "--config",
                str(ROOT / "configs" / "analysis.json"),
            ]
        )
        == 1
    )
    assert "error:" in capsys.readouterr().err


def test_input_fingerprint_is_stable():
    assert (
        load_timeline(FIXTURE, 0).source_fingerprint == load_timeline(FIXTURE, 0).source_fingerprint
    )
