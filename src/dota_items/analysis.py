"""Facts first: no purchase judgement or inferred inventory."""

from .domain import AnalysisResult, FirstRecord, PlayerTimeline


def analyze(timeline: PlayerTimeline, candidate_items: list[str]) -> AnalysisResult:
    candidates = list(dict.fromkeys(candidate_items))
    wanted = set(candidates)
    records: dict[str, FirstRecord] = {}
    for event in sorted(timeline.events, key=lambda event: event.time_seconds):
        if event.item_key in wanted and event.item_key not in records:
            records[event.item_key] = FirstRecord(
                item_key=event.item_key,
                time_seconds=event.time_seconds,
                source_event_ref=event.source_event_ref,
            )
    return AnalysisResult(
        timeline=timeline,
        first_records=sorted(records.values(), key=lambda record: record.time_seconds),
        candidate_items=candidates,
        limitations=[
            "时间表示购买日志首次记录，不等于合成完成、送达或可用时间。",
            "未记录不等于未购买；日志完整性尚未得到保证。",
            "当前版本只重建事实，尚未实现参考组、相似案例或出装推荐。",
        ],
    )
