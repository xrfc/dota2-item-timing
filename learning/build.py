"""Generate an offline learning explorer from the project's actual task roadmap."""

import argparse
import hashlib
import json
import re
import tomllib
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


TASK_ID = r"(?:ML|[LDVECUSXW])\d{2}"
STATES = {
    "待做": "pending",
    "待实现": "pending",
    "待开发": "pending",
    "进行中": "in_progress",
    "待验收": "in_progress",
    "部分": "partial",
    "部分完成": "partial",
    "已完成": "done",
    "完成": "done",
    "已实现": "done",
    "阻塞": "blocked",
}
STAGES = [
    ("evidence", "问题与证据", "明确学什么，以及数据为什么可信", ["L01", "L02", "L03"]),
    ("quality", "清洗与划分", "让缺失、时间与独立比赛成为显式规则", ["L04", "L05", "L06"]),
    ("samples", "样本与预处理", "把历史输入和未来标签变成可追溯样本", ["L07", "L08", "L09", "L10"]),
    ("audit", "审计与恢复", "检验泄漏、版本和失败恢复", ["L11", "L12"]),
]


def parse_roadmap(text: str) -> list[dict[str, Any]]:
    """Read existing table and checkbox task formats without interpreting prose as tasks."""
    tasks: dict[str, dict[str, Any]] = {}
    section = ""

    def add(task: dict[str, Any]) -> None:
        if task["id"] in tasks:
            raise ValueError(f"Duplicate roadmap task: {task['id']}")
        task["section"] = section
        tasks[task["id"]] = task

    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        checkbox = re.match(rf"^- \[([ xX])\] \*?\*?({TASK_ID})[：:]\s*(.+)", line)
        if checkbox:
            checked, task_id, description = checkbox.groups()
            add(
                {
                    "id": task_id,
                    "title": description.rstrip("*"),
                    "description": description.rstrip("*"),
                    "status": "done" if checked.lower() == "x" else "pending",
                    "source_status": "已完成" if checked.lower() == "x" else "待做",
                    "acceptance": "",
                    "dependencies": [],
                    "mapping": "",
                }
            )
            continue
        if not line.startswith("|"):
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        if not cells:
            continue
        identifier = re.match(rf"^({TASK_ID})(?:\s|$)", cells[0])
        if not identifier:
            continue
        task_id = identifier.group(1)
        if len(cells) not in (3, 4):
            raise ValueError(f"Expected three or four columns for {task_id}")
        if re.match(rf"^{TASK_ID}\s*/", cells[0]):
            if len(cells) != 4:
                raise ValueError(f"Expected four learning columns for {task_id}")
            source_status = cells[0].split("/", 1)[1].strip()
            description, mapping, acceptance = cells[1:]
            title = description.split("：", 1)[0]
            dependencies = re.findall(r"\bL\d{2}\b", mapping)
        else:
            title = cells[0][len(task_id) :].strip()
            source_status = cells[1].split("，", 1)[0].strip()
            description = cells[2]
            acceptance = cells[3] if len(cells) == 4 else ""
            mapping, dependencies = "", []
        state = STATES.get(source_status)
        if state is None:
            raise ValueError(f"Unknown status for {task_id}: {source_status}")
        add(
            {
                "id": task_id,
                "title": title,
                "description": description,
                "status": state,
                "source_status": source_status,
                "acceptance": acceptance,
                "dependencies": sorted(set(dependencies)),
                "mapping": mapping,
            }
        )
    if not tasks:
        raise ValueError("No supported task rows found in the roadmap")
    for task in tasks.values():
        if any(dependency not in tasks for dependency in task["dependencies"]):
            raise ValueError(f"Unknown dependency for {task['id']}")

    def visit(task_id: str, chain: tuple[str, ...] = ()) -> None:
        if task_id in chain:
            raise ValueError(f"Cyclic task dependency: {task_id}")
        for dependency in tasks[task_id]["dependencies"]:
            visit(dependency, (*chain, task_id))

    for task in tasks.values():
        visit(task["id"])
    return list(tasks.values())


def component_state(states: list[str]) -> str:
    if all(state == "done" for state in states):
        return "ready"
    if any(state in ("partial", "done", "in_progress") for state in states):
        return "partial"
    if any(state == "blocked" for state in states):
        return "blocked"
    return "planned"


def build_learning_data(
    roadmap: Path, learning_roadmap: Path, workspace: Path | None = None
) -> dict[str, Any]:
    engineering = parse_roadmap(roadmap.read_text(encoding="utf-8"))
    practice = parse_roadmap(learning_roadmap.read_text(encoding="utf-8"))
    for task in engineering:
        task["track"] = "engineering"
    for task in practice:
        task["track"] = "learning"
    tasks = engineering + practice
    indexed = {task["id"]: task for task in tasks}
    if len(indexed) != len(tasks):
        raise ValueError("Task IDs must be unique across engineering and learning roadmaps")
    assets = ROOT / "assets"
    catalog = json.loads((assets / "catalog.json").read_text(encoding="utf-8"))
    for component in catalog["components"]:
        references = component["tasks"] + component["learning"]
        missing = [task_id for task_id in references if task_id not in indexed]
        if missing:
            raise ValueError(f"Roadmap is missing component tasks: {', '.join(missing)}")
        if not component["tasks"] or any(
            indexed[key]["track"] != "engineering" for key in component["tasks"]
        ):
            raise ValueError("Component readiness must reference engineering tasks only")
        if any(indexed[key]["track"] != "learning" for key in component["learning"]):
            raise ValueError("Component practice links must reference learning tasks only")
        component["state"] = component_state([indexed[key]["status"] for key in component["tasks"]])
    stages = [
        {"id": key, "title": title, "description": description, "tasks": task_ids}
        for key, title, description, task_ids in STAGES
    ]
    grouped = {key for stage in stages for key in stage["tasks"]}
    if any(key not in indexed or indexed[key]["track"] != "learning" for key in grouped):
        raise ValueError("Learning roadmap is missing a required stage task")
    extras = [
        task["id"] for task in tasks if task["id"].startswith("L") and task["id"] not in grouped
    ]
    if extras:
        stages.append(
            {
                "id": "new",
                "title": "新增学习任务",
                "description": "来自更新后的 roadmap",
                "tasks": extras,
            }
        )
    summary: dict[str, Any] = {"available": False, "reason": "工作区尚未初始化"}
    if workspace is not None and (workspace / "workspace.json").exists():
        try:
            catalog_data = json.loads((workspace / "catalog.json").read_text(encoding="utf-8"))
            if not isinstance(catalog_data, dict) or not isinstance(
                catalog_data.get("matches"), dict
            ):
                raise ValueError("catalog.matches must be a match mapping")

            def count(folder: str) -> int:
                path = workspace / folder
                return sum(item.is_dir() for item in path.iterdir()) if path.is_dir() else 0

            summary = {
                "available": True,
                "matches": len(catalog_data["matches"]),
                **{folder: count(folder) for folder in ("datasets", "runs", "models", "reviews")},
            }
        except (OSError, ValueError, KeyError, TypeError) as error:
            summary = {"available": False, "reason": f"工作区摘要不可读：{error}"}
    return {
        "schema_version": "coach-learning/1",
        "version": tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["version"],
        "learning_version": "1.0.0",
        "generated_at": now(),
        "roadmap_sha256": file_hash(roadmap),
        "learning_roadmap_sha256": file_hash(learning_roadmap),
        "roadmap_name": roadmap.name,
        "tasks": tasks,
        "stages": stages,
        "workspace": summary,
        **catalog,
    }


def render_learning(data: dict[str, Any]) -> str:
    assets = ROOT / "assets"
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    for character, replacement in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        payload = payload.replace(character, replacement)
    substitutions = {
        "{{CSS}}": (assets / "learning.css").read_text(encoding="utf-8"),
        "{{JS}}": (assets / "learning.js").read_text(encoding="utf-8"),
        "{{LABS}}": (assets / "labs.js").read_text(encoding="utf-8"),
        "{{DATA}}": payload,
        "{{VERSION}}": escape(data["version"]),
    }
    html = (assets / "learning.html").read_text(encoding="utf-8")
    # A single substitution pass prevents user-controlled task text becoming a template token.
    return re.sub(
        r"\{\{(?:CSS|JS|LABS|DATA|VERSION)\}\}", lambda match: substitutions[match[0]], html
    )


def generate_learning(
    roadmap: Path, learning_roadmap: Path, output: Path, workspace: Path | None = None
) -> dict[str, Any]:
    for source in (roadmap, learning_roadmap):
        if not source.is_file():
            raise ValueError(f"Roadmap not found: {source}")
    manifest = output.with_suffix(".manifest.json")
    if any(
        path.resolve() == source.resolve()
        for path in (output, manifest)
        for source in (roadmap, learning_roadmap)
    ):
        raise ValueError("Learning output cannot overwrite a source roadmap")
    data = build_learning_data(roadmap, learning_roadmap, workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_learning(data), encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                key: data[key]
                for key in (
                    "schema_version",
                    "version",
                    "learning_version",
                    "generated_at",
                    "roadmap_sha256",
                    "learning_roadmap_sha256",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    learning_tasks = [task for task in data["tasks"] if task["id"].startswith("L")]
    return {
        "page": str(output.resolve()),
        "manifest": str(manifest.resolve()),
        "roadmap_sha256": data["roadmap_sha256"],
        "learning_tasks": len(learning_tasks),
        "completed_learning_tasks": sum(task["status"] == "done" for task in learning_tasks),
        "note": "Offline learning page; engineering and practice progress use separate roadmaps.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the independent offline learning explorer")
    parser.add_argument("--roadmap", type=Path, default=PROJECT / "docs" / "roadmap.md")
    parser.add_argument("--learning-roadmap", type=Path, default=ROOT / "docs" / "roadmap.md")
    parser.add_argument("--workspace", type=Path, help="Optional read-only workspace summary")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "index.html")
    args = parser.parse_args()
    try:
        result = generate_learning(args.roadmap, args.learning_roadmap, args.output, args.workspace)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"error: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
