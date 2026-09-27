"""Self-contained HTML; escape all external labels."""

from html import escape

from .domain import AnalysisResult


def format_time(seconds: float) -> str:
    sign = "−" if seconds < 0 else ""
    minutes, remainder = divmod(int(abs(seconds)), 60)
    return f"{sign}{minutes:02d}:{remainder:02d}"


def render_html(result: AnalysisResult) -> str:
    timeline = result.timeline
    first = {record.item_key: record for record in result.first_records}
    cards = "".join(
        "<article><span>"
        + escape(key)
        + "</span><strong>"
        + (format_time(first[key].time_seconds) if key in first else "无记录")
        + "</strong></article>"
        for key in result.candidate_items
    )
    rows = (
        "".join(
            f"<tr><td>{format_time(event.time_seconds)}</td><td>{escape(event.item_key)}</td>"
            f"<td><code>{escape(event.source_event_ref)}</code></td></tr>"
            for event in timeline.events
        )
        or '<tr><td colspan="3">没有可展示的购买记录，请检查数据质量。</td></tr>'
    )
    flags = "".join(f"<li>{escape(flag)}</li>" for flag in timeline.quality_flags)
    limits = "".join(f"<li>{escape(item)}</li>" for item in result.limitations)
    return f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DOTA2 出装时间线 · {timeline.match_id}</title>
<style>
body{{margin:0;background:#111923;color:#e7eef6;font:16px/1.7 system-ui,sans-serif}}
main{{max-width:1000px;margin:40px auto;padding:0 24px}}
h1{{font-size:32px}} h2{{margin-top:32px}} .muted,span{{color:#a9bacd}}
.cards{{display:flex;flex-wrap:wrap;gap:12px}}
article{{padding:18px;background:#1c2a39;border-radius:12px;min-width:150px}}
article strong{{display:block;color:#7de0bd;font-size:26px}}
table{{width:100%;border-collapse:collapse}} td,th{{text-align:left;padding:12px}}
tr{{border-bottom:1px solid #304156}} code{{overflow-wrap:anywhere;font-size:12px}}
.notice{{border-left:3px solid #7de0bd;padding:12px 16px;background:#1c2a39}}
</style><main>
<p class="muted">DOTA2 ITEM TIMING · v0.1</p><h1>装备日志时间线</h1>
<p>比赛 {timeline.match_id} · 玩家槽位 {timeline.player_slot} · 英雄 ID {timeline.hero_id}
· 版本 ID {timeline.patch_id} · 时长 {format_time(timeline.duration_seconds)}</p>
<p class="notice">这是日志事实报告。装备时间差本身不能证明出装是否合理。</p>
<h2>候选装备首次记录</h2><div class="cards">{cards}</div>
<h2>全部购买记录</h2><table><thead><tr><th>时间</th><th>装备 key</th>
<th>原始证据位置</th></tr></thead><tbody>{rows}</tbody></table>
<h2>数据质量</h2><p>日志状态：{escape(timeline.purchase_log_status)}</p>
<ul>{flags or "<li>格式检查通过；事件语义仍需人工复核。</li>"}</ul>
<h2>解释范围</h2><ul>{limits}</ul>
<p class="muted">来源：{escape(timeline.source)}<br>
<code>{escape(timeline.source_fingerprint)}</code></p></main></html>"""
