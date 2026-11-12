PYTHON ?= $(wildcard .venv/bin/python)
ifeq ($(PYTHON),)
PYTHON := python3
endif
RUFF ?= $(wildcard .venv/bin/ruff)
ifeq ($(RUFF),)
RUFF := ruff
endif

.PHONY: venv hooks lint test ci pdf

venv:
	bash scripts/setup-venv.sh

# Use the repo's git hooks (rebuilds the lab guide PDFs on commit). Run once per clone.
hooks:
	git config core.hooksPath .githooks

lint:
	$(RUFF) check .
	$(RUFF) format --check .

test:
	$(PYTHON) test_server.py
	$(PYTHON) test_repo.py

ci: lint test

# Stamp today's date into the guide, then rebuild docs/spaces-lab-guide.pdf and -dark.pdf.
# Set CHROME to pick a browser.
pdf:
	$(PYTHON) scripts/build_pdfs.py
