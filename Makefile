.PHONY: setup build serve test verify footage gemini-check gemini-smoke gemini-replay detection-setup detect camera-refresh tunnel tunnel-status tunnel-stop

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
	python3 clearway/scripts/fetch_person_footage.py

detection-setup:
	clearway/.venv/bin/python -m pip install -r clearway/detection-requirements.txt

detect:
	clearway/.venv/bin/python clearway/scripts/run_detection.py --source all --download-model

camera-refresh:
	python3 clearway/scripts/refresh_camera_context.py

tunnel:
	clearway/.venv/bin/python clearway/scripts/tunnel.py start

tunnel-status:
	clearway/.venv/bin/python clearway/scripts/tunnel.py status

tunnel-stop:
	clearway/.venv/bin/python clearway/scripts/tunnel.py stop

gemini-check:
	clearway/.venv/bin/python clearway/scripts/check_gemini.py

gemini-smoke:
	clearway/.venv/bin/python clearway/scripts/run_gemini.py

gemini-replay:
	clearway/.venv/bin/python clearway/scripts/run_gemini.py --cached-only
