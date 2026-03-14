PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

.PHONY: setup install run migrate makemigrations test lint check

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && pip install --upgrade pip
	$(ACTIVATE) && pip install -r requirements/dev.txt

install:
	$(ACTIVATE) && pip install -r requirements/dev.txt

run:
	$(ACTIVATE) && $(PYTHON) manage.py runserver

migrate:
	$(ACTIVATE) && $(PYTHON) manage.py migrate

makemigrations:
	$(ACTIVATE) && $(PYTHON) manage.py makemigrations

test:
	$(ACTIVATE) && $(PYTHON) manage.py test

lint:
	$(ACTIVATE) && ruff check .

check:
	$(ACTIVATE) && $(PYTHON) manage.py check
	$(ACTIVATE) && $(PYTHON) manage.py makemigrations --check --dry-run
