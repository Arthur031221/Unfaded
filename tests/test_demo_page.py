"""Opens the GitHub Pages build of the interface in a real browser."""

from __future__ import annotations

import http.server
import importlib.util
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = module.build(tmp_path_factory.mktemp("pages") / "site")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), partial(Quiet, directory=str(target)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except Exception:
            instance = p.chromium.launch(channel="chrome")
        yield instance
        instance.close()


def test_demo_page_loads_switches_language_and_opens_an_example(site, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    problems: list[str] = []
    page.on("pageerror", lambda err: problems.append(str(err)))
    page.on("console", lambda msg: problems.append(msg.text) if msg.type == "error" else None)
    page.goto(site, wait_until="networkidle")

    english = page.inner_text("body")
    assert "Unfaded" in english

    page.locator("#lang").select_option("ja")
    page.wait_for_timeout(500)
    assert page.inner_text("body") != english
    assert page.evaluate("document.documentElement.lang") == "ja"

    page.locator("button.example").first.click()
    page.wait_for_timeout(1500)
    assert page.locator("#step-list > *").count() >= 5
    assert problems == []
    page.close()
