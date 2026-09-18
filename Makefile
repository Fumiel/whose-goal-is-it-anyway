PYTHON ?= python3
PYTHONPATH := src

.PHONY: check-fast check validate dry-run clean-generated

check-fast:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests
	$(PYTHON) -m compileall -q src tests

check: check-fast
	ruff check .
	ruff format --check .
	pytest
	$(MAKE) validate

validate:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m goal_takeover.cli validate-repository

dry-run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m goal_takeover.cli synthetic-dry-run \
		--artifact-root artifacts --run-id synthetic_dry_run

clean-generated:
	find src tests -type d -name __pycache__ -prune -exec rm -rf {} +
	find src -type d -name '*.egg-info' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
	find . -path ./.git -prune -o -name .DS_Store -type f -delete
