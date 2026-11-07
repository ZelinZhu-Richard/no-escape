.PHONY: setup build serve test verify footage

setup:
	python3 -m venv clearway/.venv
	clearway/.venv/bin/python -m pip install -r clearway/requirements-dev.txt
	cd clearway/web && npm ci --cache .npm-cache

build:
	cd clearway/web && npm run build

serve:
	python3 clearway/scripts/serve.py

test:
	cd clearway && .venv/bin/python -m pytest -q
	cd clearway/web && npm test
	cd clearway/web && npm run build

verify:
	python3 clearway/scripts/verify_cycles.py

footage:
	python3 clearway/scripts/fetch_footage.py --with-control
