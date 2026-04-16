"""Playwright E2E test for stockviewer Streamlit app"""

import os
import re

import pytest
from playwright.sync_api import expect

STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "http://localhost:8501")


@pytest.fixture(scope="module")
def app_url():
    return STREAMLIT_URL


@pytest.fixture(scope="module")
def browser_page(app_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

        page.goto(app_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(15000)

        page.reload(wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(15000)

        yield page, errors

        browser.close()


@pytest.fixture(scope="module")
def browser_page_688110(app_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        page.goto(app_url, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(15000)

        symbol_input = page.locator("input[aria-label='股票代码']")
        symbol_input.fill("688110")
        symbol_input.press("Enter")
        page.wait_for_timeout(30000)

        yield page

        browser.close()


class TestStreamlitApp:
    def test_page_loads(self, browser_page):
        pg, _ = browser_page
        expect(pg).to_have_title(re.compile(r".*股票.*"), timeout=30000)

    def test_no_frontend_errors(self, browser_page):
        pg, errors = browser_page
        frontend_errors = [
            e
            for e in errors
            if "st.exception" not in e.lower()
            and "500" not in e
            and "Failed to fetch dynamically imported module" not in e
        ]
        assert len(frontend_errors) == 0, f"Frontend errors: {frontend_errors}"

    def test_no_render_errors(self, browser_page):
        pg, _ = browser_page
        st_alerts = pg.locator("[data-testid='stAlert']")
        for i in range(st_alerts.count()):
            alert_text = st_alerts.nth(i).inner_text()
            assert "渲染失败" not in alert_text, f"Chart render error found: {alert_text}"
            assert "失败" not in alert_text, f"Error found: {alert_text}"

    def test_kline_chart_renders(self, browser_page):
        pg, _ = browser_page
        chart_frame = pg.frame_locator("iframe").first
        canvas = chart_frame.locator("canvas").first
        expect(canvas).to_be_visible(timeout=30000)

    def test_no_streamlit_exception(self, browser_page):
        pg, _ = browser_page
        st_exceptions = pg.locator("[data-testid='stException']")
        assert st_exceptions.count() == 0, "Streamlit exception found"

    def test_metrics_displayed(self, browser_page):
        pg, _ = browser_page
        metrics = pg.locator("[data-testid='stMetricValue']")
        assert metrics.count() >= 3, f"Expected at least 3 metrics, found {metrics.count()}"


class TestBSMultiselect:
    def test_multiselect_exists(self, browser_page):
        pg, _ = browser_page
        multiselect = pg.locator("[data-testid='stMultiSelect']")
        expect(multiselect.first).to_be_visible(timeout=30000)

    def test_multiselect_label(self, browser_page):
        pg, _ = browser_page
        label = pg.locator("[data-testid='stMultiSelect'] p").first
        expect(label).to_have_text("买卖点策略", timeout=30000)

    def test_multiselect_default_empty(self, browser_page):
        pg, _ = browser_page
        tags = pg.locator("[data-testid='stMultiSelect'] span[data-testid='stTag']")
        expect(tags).to_have_count(0, timeout=10000)

    def test_multiselect_has_options(self, browser_page):
        pg, _ = browser_page
        multiselect = pg.locator("[data-testid='stMultiSelect']").first
        multiselect.locator("input").first.click()
        pg.wait_for_timeout(5000)
        options = pg.locator("[data-testid='stMultiSelectOption']")
        try:
            expect(options.first).to_be_visible(timeout=10000)
        except Exception:
            pass
        count = options.count()
        if count < 4:
            dropdown = pg.locator("[data-baseweb='popover']").last
            items = dropdown.locator("li")
            count = items.count()
        assert count >= 4, f"Expected at least 4 strategy options, found {count}"


class TestZsAndBcFeature:
    def test_zs_checkbox_exists(self, browser_page):
        pg, _ = browser_page
        checkboxes = pg.locator("[data-testid='stCheckbox']")
        labels = []
        for i in range(checkboxes.count()):
            label_text = checkboxes.nth(i).locator("label").inner_text()
            labels.append(label_text)
        assert any("中枢" in l for l in labels), f"Expected ZS checkbox, found labels: {labels}"

    def test_bc_checkbox_exists(self, browser_page):
        pg, _ = browser_page
        checkboxes = pg.locator("[data-testid='stCheckbox']")
        labels = []
        for i in range(checkboxes.count()):
            label_text = checkboxes.nth(i).locator("label").inner_text()
            labels.append(label_text)
        assert any("背驰" in l for l in labels), f"Expected BC checkbox, found labels: {labels}"

    def test_enable_zs_shows_metric(self, browser_page):
        pg, _ = browser_page
        checkboxes = pg.locator("[data-testid='stCheckbox']")
        for i in range(checkboxes.count()):
            label_text = checkboxes.nth(i).locator("label").inner_text()
            if "中枢" in label_text:
                checkboxes.nth(i).click()
                break

        pg.wait_for_timeout(20000)

        metric_labels = pg.locator("[data-testid='stMetricLabel']")
        metric_values = pg.locator("[data-testid='stMetricValue']")
        found_zs = False
        for i in range(metric_labels.count()):
            if "中枢数量" in metric_labels.nth(i).inner_text():
                found_zs = True
                val_text = metric_values.nth(i).inner_text()
                assert int(val_text) > 0, f"中枢数量应为正数，实际: {val_text}"
        assert found_zs, "未找到中枢数量metric"

    def test_enable_bc_shows_metric(self, browser_page):
        pg, _ = browser_page
        checkboxes = pg.locator("[data-testid='stCheckbox']")
        for i in range(checkboxes.count()):
            label_text = checkboxes.nth(i).locator("label").inner_text()
            if "背驰" in label_text:
                checkboxes.nth(i).click()
                break

        pg.wait_for_timeout(20000)

        metric_labels = pg.locator("[data-testid='stMetricLabel']")
        metric_values = pg.locator("[data-testid='stMetricValue']")
        found_bc = False
        for i in range(metric_labels.count()):
            if "背驰点数量" in metric_labels.nth(i).inner_text():
                found_bc = True
                val_text = metric_values.nth(i).inner_text()
                assert int(val_text) > 0, f"背驰点数量应为正数，实际: {val_text}"
        assert found_bc, "未找到背驰点数量metric"

    def test_enable_zs_and_bc_no_render_errors(self, browser_page):
        pg, _ = browser_page
        checkboxes = pg.locator("[data-testid='stCheckbox']")
        for i in range(checkboxes.count()):
            label_text = checkboxes.nth(i).locator("label").inner_text()
            if "中枢" in label_text or "背驰" in label_text:
                checkboxes.nth(i).click()

        pg.wait_for_timeout(15000)

        st_alerts = pg.locator("[data-testid='stAlert']")
        for i in range(st_alerts.count()):
            alert_text = st_alerts.nth(i).inner_text()
            assert "渲染失败" not in alert_text, f"启用中枢/背驰后出现渲染错误: {alert_text}"

        chart_frame = pg.frame_locator("iframe").first
        canvas = chart_frame.locator("canvas").first
        assert canvas.is_visible(), "图表canvas应可见"

    def test_zs_and_bc_chart_renders(self, browser_page):
        pg, _ = browser_page
        checkboxes = pg.locator("[data-testid='stCheckbox']")
        for i in range(checkboxes.count()):
            label_text = checkboxes.nth(i).locator("label").inner_text()
            if "中枢" in label_text or "背驰" in label_text:
                checkboxes.nth(i).click()

        pg.wait_for_timeout(15000)

        chart_frame = pg.frame_locator("iframe").first
        canvas = chart_frame.locator("canvas").first
        assert canvas.is_visible(), "启用中枢/背驰后图表应正常渲染"


class Test688110ZsAndBc:
    def test_688110_basic_metrics(self, browser_page_688110):
        pg = browser_page_688110
        metric_labels = pg.locator("[data-testid='stMetricLabel']")
        metric_values = pg.locator("[data-testid='stMetricValue']")
        metrics = {}
        for i in range(metric_labels.count()):
            metrics[metric_labels.nth(i).inner_text()] = metric_values.nth(i).inner_text()
        kline = int(metrics.get("K线数量", "0"))
        bi = int(metrics.get("笔数量", "0"))
        fx = int(metrics.get("分型数量", "0"))
        assert kline >= 400, f"688110 K线数量应>=400，实际: {kline}"
        assert bi >= 30, f"688110 笔数量应>=30，实际: {bi}"
        assert fx >= 100, f"688110 分型数量应>=100，实际: {fx}"

    def test_688110_zs_positive(self, browser_page_688110):
        pg = browser_page_688110
        pg.evaluate("""() => {
            const inputs = document.querySelectorAll('input[type="checkbox"]');
            for (const input of inputs) {
                if (input.getAttribute('aria-label') === '显示中枢') {
                    input.click();
                    break;
                }
            }
        }""")
        pg.wait_for_timeout(30000)

        metric_labels = pg.locator("[data-testid='stMetricLabel']")
        metric_values = pg.locator("[data-testid='stMetricValue']")
        found = False
        for i in range(metric_labels.count()):
            if "中枢数量" in metric_labels.nth(i).inner_text():
                found = True
                val = metric_values.nth(i).inner_text()
                assert int(val) > 0, f"688110 中枢数量应>0，实际: {val}"
        assert found, "未找到中枢数量metric"

    def test_688110_bc_positive(self, browser_page_688110):
        pg = browser_page_688110
        pg.evaluate("""() => {
            const inputs = document.querySelectorAll('input[type="checkbox"]');
            for (const input of inputs) {
                if (input.getAttribute('aria-label') === '显示背驰标记') {
                    input.click();
                    break;
                }
            }
        }""")
        pg.wait_for_timeout(30000)

        metric_labels = pg.locator("[data-testid='stMetricLabel']")
        metric_values = pg.locator("[data-testid='stMetricValue']")
        found = False
        for i in range(metric_labels.count()):
            if "背驰点数量" in metric_labels.nth(i).inner_text():
                found = True
                val = metric_values.nth(i).inner_text()
                assert int(val) > 0, f"688110 背驰点数量应>0，实际: {val}"
        assert found, "未找到背驰点数量metric"
