"""Optional real-browser acceptance checks; Playwright is a learning-only test dependency."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def range_value(page, selector: str, value: int) -> None:
    page.locator(selector).evaluate(
        "(element, value) => { element.value = value; "
        "element.dispatchEvent(new Event('input', {bubbles:true})); }",
        value,
    )


def check_page(page, output: Path) -> None:
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(output.as_uri())
    data = json.loads(page.locator("#learning-data").text_content())
    workflows = [task for task in data["tasks"] if task["id"].startswith("W")]
    expected_workflow = f"{sum(task['status'] == 'done' for task in workflows)} / {len(workflows)}"
    practice_count = sum(task["track"] == "learning" for task in data["tasks"])
    expected_practice = f"0 / {practice_count}"
    component_count = len(data["components"])
    expect(page.locator("#workflow-count")).to_have_text(expected_workflow)
    expect(page.locator("#task-count")).to_have_text(expected_practice)
    expect(page.locator("[data-component]")).to_have_count(component_count)

    page.locator('[data-component="dataset"]').click()
    page.locator("#learn-component").check()
    expect(page.locator("#personal-count")).to_have_text(f"1 / {component_count}")
    expect(page.locator("#task-count")).to_have_text(expected_practice)
    page.locator("#next-task").click()
    note = "</textarea><script>window.injected=true</script>因果时间边界"
    page.locator("#task-note").fill(note)
    page.locator("#review-task").check()
    expect(page.locator("#task-note")).to_have_value(note)
    assert page.evaluate("window.injected === undefined")
    expect(page.locator("#task-count")).to_have_text(expected_practice)
    page.locator('[data-filter="ready"]').click()
    expect(page.locator('#task-list [data-task="L01"]')).to_be_visible()
    page.locator('[data-filter="done"]').click()
    expect(page.locator("#task-list [data-task]")).to_have_count(0)
    page.locator('[data-filter="all"]').click()
    page.locator("#search").fill("L09")
    expect(page.locator('#task-list [data-task="L09"]')).to_be_visible()
    page.locator('#task-list [data-task="L09"]').click()
    expect(page.locator("#task-detail")).to_contain_text("L09")

    page.locator('[data-view="choices"]').click()
    expect(page.locator(".choice-card")).to_have_count(len(data["choices"]))
    page.locator("#search").fill("Python")
    expect(page.locator("#choice-python")).to_be_visible()
    page.locator('[data-view="lab"]').click()
    expect(page.locator("#asof-results")).to_contain_text("金币：1200")
    range_value(page, "#max-age", 1)
    expect(page.locator("#asof-results").locator(".asof-result").first).to_contain_text(
        "金币：缺失"
    )
    range_value(page, "#cutoff", 590)
    expect(page.locator("#asof-results")).to_contain_text("金币：0")
    page.locator("#missing-gold").check()
    expect(page.locator("#asof-results")).to_contain_text("没有历史观测")
    page.locator("#split-window").click()
    expect(page.locator("#split-result")).to_contain_text("6 / 6 场")
    page.locator("#split-group").click()
    expect(page.locator("#split-result")).to_contain_text("0 / 6 场")
    expect(page.locator("#fit-result strong").first).to_have_text("200.00")
    range_value(page, "#holdout", 2000)
    expect(page.locator("#fit-result strong").first).to_have_text("200.00")
    page.locator("#fit-all").click()
    expect(page.locator("#fit-result strong").first).to_have_text("650.00")

    with page.expect_download() as captured:
        page.locator("#export-progress").click()
    record = json.loads(Path(captured.value.path()).read_text(encoding="utf-8"))
    assert record["learned_components"] == ["dataset"]
    assert record["reviewed_tasks"] == ["L01"]
    assert record["notes"]["L01"] == note
    assert "engineering_status" not in record
    record["learned_components"] = ["ingest", "dataset"]
    page.locator("#progress-file").set_input_files(
        {
            "name": "record.json",
            "mimeType": "application/json",
            "buffer": json.dumps(record).encode(),
        }
    )
    expect(page.locator("#personal-count")).to_have_text(f"2 / {component_count}")
    expect(page.locator("#task-count")).to_have_text(expected_practice)
    page.locator("#progress-file").set_input_files(
        {"name": "bad.json", "mimeType": "application/json", "buffer": b"{}"}
    )
    expect(page.locator("#toast")).to_contain_text("格式不正确")
    expect(page.locator("#personal-count")).to_have_text(f"2 / {component_count}")

    page.reload()
    expect(page.locator("#personal-count")).to_have_text(f"2 / {component_count}")
    page.locator("#next-task").click()
    expect(page.locator("#task-note")).to_have_value(note)
    page.locator('[data-view="architecture"]').click()
    screenshots = ROOT / "output" / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    for view in ("path", "choices", "lab", "architecture"):
        page.locator(f'[data-view="{view}"]').click()
        expect(page.locator("#export-progress")).to_be_visible()
        expect(page.locator("#import-progress")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), view
    page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
    assert not errors, errors


def main() -> None:
    (ROOT / "output").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "output", prefix="browser-") as folder:
        output = Path(folder) / "index.html"
        practice = Path(folder) / "practice.md"
        # An isolated pending-task fixture keeps actual learning progress out of UI tests.
        text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        practice.write_text(
            re.sub(r"(\| L\d{2} / )[^|]+(?=\|)", r"\1待做 ", text), encoding="utf-8"
        )
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(ROOT / "build.py"),
                "--learning-roadmap",
                str(practice),
                "--output",
                str(output),
            ],
            check=True,
            capture_output=True,
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            check_page(context.new_page(), output)
            context.close()
            browser.close()
    print(
        "Browser checks passed: navigation, progress, notes, filters, labs, import/export, mobile."
    )


if __name__ == "__main__":
    main()
