"""Root conftest.py -- session-scoped fixtures and QA log integration."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytest
import pytest_asyncio

from smfs_qa.client import SMFSClient
from smfs_qa.logger import QALogger
from smfs_qa.routes import HealthRoute, MarketsRoute, OrdersRoute, SnapshotRoute, StatsRoute
from smfs_qa.ws_routes import MarketFeedRoute, SolanaStreamRoute

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

PROJECT_ROOT = Path(__file__).parent
ALLURE_DIR = PROJECT_ROOT / "allure"
ALLURE_RESULTS = PROJECT_ROOT / "allure-results"
ALLURE_REPORT = PROJECT_ROOT / "allure-report"


def pytest_configure(config):
    """Copy allure metadata files into allure-results before tests run."""
    ALLURE_RESULTS.mkdir(exist_ok=True)
    for name in ("environment.properties", "categories.json", "executor.json"):
        src = ALLURE_DIR / name
        if src.exists():
            shutil.copy2(src, ALLURE_RESULTS / name)

    _preserve_allure_history()


def _preserve_allure_history():
    """Copy previous report history into allure-results so the Trend widget works."""
    history_src = ALLURE_REPORT / "history"
    history_dst = ALLURE_RESULTS / "history"
    if history_src.is_dir():
        if history_dst.exists():
            shutil.rmtree(history_dst)
        shutil.copytree(history_src, history_dst)


_DEFAULT_HOST = "interviews-api.sonic.game"
BASE_URL = os.environ.get("SMFS_BASE_URL", f"https://{_DEFAULT_HOST}")
WS_BASE_URL = os.environ.get("SMFS_WS_URL", f"wss://{_DEFAULT_HOST}")


# --- QA Logger auto-attach per test ---


@pytest.fixture(autouse=True)
def _qa_log_per_test(request):
    """Reset QA logger before each test; attach log to Allure after."""
    QALogger.reset()
    QALogger.info(f"TEST START: {request.node.nodeid}")
    yield
    QALogger.info(f"TEST END: {request.node.nodeid}")
    QALogger.flush_to_allure(name=f"QA Log: {request.node.name}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture failure details and attach to Allure."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        QALogger.log_failure(item.name, Exception(str(report.longrepr)[:500]))


# --- Session fixtures ---


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def ws_base_url() -> str:
    return WS_BASE_URL


@pytest_asyncio.fixture
async def api_client(base_url: str) -> SMFSClient:
    async with SMFSClient(base_url) as client:
        yield client


# --- Route model fixtures ---


@pytest.fixture
def health_route(api_client: SMFSClient) -> HealthRoute:
    return HealthRoute(api_client)


@pytest.fixture
def markets_route(api_client: SMFSClient) -> MarketsRoute:
    return MarketsRoute(api_client)


@pytest.fixture
def snapshot_route(api_client: SMFSClient) -> SnapshotRoute:
    return SnapshotRoute(api_client)


@pytest.fixture
def orders_route(api_client: SMFSClient) -> OrdersRoute:
    return OrdersRoute(api_client)


@pytest.fixture
def stats_route(api_client: SMFSClient) -> StatsRoute:
    return StatsRoute(api_client)


@pytest.fixture
def market_feed_route(ws_base_url: str) -> MarketFeedRoute:
    return MarketFeedRoute(ws_base_url)


@pytest.fixture
def solana_stream_route(ws_base_url: str) -> SolanaStreamRoute:
    return SolanaStreamRoute(ws_base_url)
