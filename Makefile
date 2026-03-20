.PHONY: install test test-rest test-ws test-solana test-perf \
       lint format typecheck report clean \
       load-test stress-test soak-test load-test-rest load-test-orders load-test-ws locust-ui

LOCUSTFILE = src/smfs_qa/locustfile.py
LOCUST_HOST = https://interviews-api.sonic.game

# --- Setup ---

install:
	pip install -e ".[test,dev]"

install-all:
	pip install -e ".[test,dev,load]"

# --- Test Suites (pytest) ---

test:
	mkdir -p results
	pytest tests/ -v --alluredir=allure-results --junitxml=results/live.xml --reruns 3

test-rest:
	pytest tests/rest/ -v --reruns 3

test-ws:
	pytest tests/websocket/ -v --reruns 3

test-solana:
	pytest tests/solana/ -v --reruns 3

test-perf:
	mkdir -p results
	pytest tests/performance/ -v -m perf --timeout 300 \
		--alluredir=allure-results/performance --junitxml=results/performance.xml

# --- Code Quality ---

lint:
	ruff check src/ tests/ conftest.py

format:
	ruff format src/ tests/ conftest.py

typecheck:
	mypy src/smfs_qa/ --ignore-missing-imports

# --- Reporting ---

report:
	@# Preserve history for Trend widget
	@if [ -d allure-report/history ]; then \
		mkdir -p allure-results/history; \
		cp -r allure-report/history/* allure-results/history/ 2>/dev/null || true; \
	fi
	@# Copy metadata files
	@cp -f allure/environment.properties allure-results/ 2>/dev/null || true
	@cp -f allure/categories.json allure-results/ 2>/dev/null || true
	@cp -f allure/executor.json allure-results/ 2>/dev/null || true
	allure generate allure-results/ -o allure-report/ --clean
	allure open allure-report/

# --- Load Testing (Locust) ---

load-test:
	mkdir -p results
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST) \
		--headless -u 50 -r 5 --run-time 60s \
		--csv=results/locust --html=results/locust_report.html

stress-test:
	mkdir -p results
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST) \
		--headless -u 100 -r 10 --run-time 120s \
		--csv=results/locust-stress --html=results/locust_stress_report.html

soak-test:
	mkdir -p results
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST) \
		--headless -u 30 -r 3 --run-time 300s \
		--csv=results/locust-soak --html=results/locust_soak_report.html

load-test-rest:
	mkdir -p results
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST) \
		--headless -u 50 -r 5 --run-time 60s --tags rest \
		--csv=results/locust-rest --html=results/locust_rest_report.html

load-test-orders:
	mkdir -p results
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST) \
		--headless -u 20 -r 5 --run-time 60s --tags orders \
		--csv=results/locust-orders --html=results/locust_orders_report.html

load-test-ws:
	mkdir -p results
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST) \
		--headless -u 20 -r 2 --run-time 60s --tags websocket \
		--csv=results/locust-ws --html=results/locust_ws_report.html

locust-ui:
	locust -f $(LOCUSTFILE) --host=$(LOCUST_HOST)

# --- Cleanup ---

clean:
	rm -rf allure-results/ allure-report/ results/ .pytest_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
