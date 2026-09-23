PYTHON ?= $(wildcard .venv/bin/python)
ifeq ($(PYTHON),)
PYTHON := python3
endif
RUFF ?= $(wildcard .venv/bin/ruff)
ifeq ($(RUFF),)
RUFF := ruff
endif

.PHONY: venv lint test ci

venv:
	bash scripts/setup-venv.sh

lint:
	$(RUFF) check .
	$(RUFF) format --check .

test:
	$(PYTHON) test_server.py
	$(PYTHON) test_repo.py

ci: lint test
