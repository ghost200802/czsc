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

        yield page, errors

        browser.close()


class TestStreamlitApp:
    def test_page_loads(self, browser_page):
        pg, _ = browser_page
        expect(pg).to_have_title(re.compile(r".*股票.*"), timeout=30000)

    def test_no_frontend_errors(self, browser_page):
        pg, errors = browser_page
        frontend_errors = [e for e in errors if "st.exception" not in e.lower()]
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
        multiselect.click()
        pg.wait_for_timeout(1000)
        options = pg.locator("[data-testid='stMultiSelectOption']")
        count = options.count()
        assert count >= 4, f"Expected at least 4 strategy options, found {count}"
