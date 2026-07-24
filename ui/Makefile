PYTHON ?= python3

.PHONY: test health backend frontend-build

test:
	PYTHONPATH=backend $(PYTHON) -m unittest discover -s backend/tests -p 'test*.py' -v

health:
	PYTHONPATH=backend $(PYTHON) -m dpo.cli --config config/project.example.yaml health

backend:
	uvicorn dpo.main:app --app-dir backend --host 127.0.0.1 --port 8000

frontend-build:
	cd frontend && npm run build
