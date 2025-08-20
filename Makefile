# ------------- Config (override at CLI: make run IN=... OUT=... POLICY=...) -------------
IN      ?= data/sample_transactions.csv
OUT     ?= out
POLICY  ?= configs/fintech_default.json

# ------------- Use venv Python for local targets -------------
VENV    ?= $(PWD)/venv
PYTHON  := $(VENV)/bin/python

.PHONY: install check-venv run run-strict run-bad audit test clean docker-build docker-run docker-run-strict

check-venv:
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "⚠️  No virtualenv active. Run: source venv/bin/activate"; \
		exit 1; \
	fi
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "⚠️  venv Python not found at $(PYTHON). Create it: python -m venv venv"; \
		exit 1; \
	fi

install: check-venv
	$(PYTHON) -m pip install -U pip
	-$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install pandas pyarrow pytest python-dateutil

# ------------- Local (venv) targets -------------
run: check-venv
	PYTHONPATH=$(PWD) $(PYTHON) -m cli.process --input $(IN) --out $(OUT) --policy $(POLICY)

run-strict: check-venv
	PYTHONPATH=$(PWD) $(PYTHON) -m cli.process --input $(IN) --out $(OUT) --policy $(POLICY) --strict

run-permissive: check-venv
	$(MAKE) run IN=data/sample_transactions_bad.csv OUT=out_permissive
	@echo "Permissive run complete. See masked data in out_permissive/ and quarantined rows in out_permissive/quarantine.csv (if any)."

run-bad: check-venv
	$(MAKE) run-strict IN=data/sample_transactions_bad.csv OUT=out_bad

audit: check-venv
	PYTHONPATH=$(PWD) $(PYTHON) -m audit.verify --out $(OUT)

test: check-venv
	PYTHONPATH=$(PWD) $(PYTHON) -m pytest -q

clean:
	rm -rf out out_bad .pytest_cache **/__pycache__ *.pyc

demo:
	$(PYTHON) -m cli.process --input data/sample_transactions.csv --out out_demo --policy configs/fintech_default.json
	$(PYTHON) audit/verify.py out_demo

demo-bad:
	$(PYTHON) -m cli.process --input data/sample_transactions_bad.csv --out out_demo_bad --policy configs/fintech_default.json || true
	$(PYTHON) audit/verify.py out_demo_bad

# ------------- Docker targets (no venv needed) -------------
docker-build:
	docker build -t privacy-layer:latest .

docker-run:
	docker run --rm \
	  -v $(PWD)/data:/app/data \
	  -v $(PWD)/$(OUT):/app/$(OUT) \
	  privacy-layer:latest \
	  --input $(IN) --out $(OUT) --policy $(POLICY)

docker-run-strict:
	docker run --rm \
	  -v $(PWD)/data:/app/data \
	  -v $(PWD)/$(OUT):/app/$(OUT) \
	  privacy-layer:latest \
	  --input $(IN) --out $(OUT) --policy $(POLICY) --strict

# Quick demos (pre-wired defaults)
docker-demo:
	docker run --rm \
		-v $(PWD):/app \
		-w /app \
		privacy-layer:latest \
		--input data/sample_transactions.csv \
		--out out_docker_good \
		--policy configs/fintech_default.json
	$(PYTHON) audit/verify.py out_docker_good

docker-demo-bad:
	docker run --rm \
		-v $(PWD):/app \
		-w /app \
		privacy-layer:latest \
		--input data/sample_transactions_bad.csv \
		--out out_docker_bad \
		--policy configs/fintech_default.json || true
	$(PYTHON) audit/verify.py out_docker_bad