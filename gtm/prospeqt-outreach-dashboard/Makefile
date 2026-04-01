.PHONY: dev test screenshots qa

PORT ?= 8099

dev:
	python server.py --port $(PORT) --no-prefetch

test:
	python -m pytest tests/ -v

screenshots:
	python qa/screenshot.py --port $(PORT) --prefix manual --wait

qa:
	python server.py --port $(PORT) --mock & echo $$! > .server.pid
	sleep 2 && python qa/screenshot.py --port $(PORT) --prefix qa --wait
	kill $$(cat .server.pid) 2>/dev/null; rm -f .server.pid
	python -m pytest tests/ -v
	@echo "QA complete. Check qa/screenshots/"
