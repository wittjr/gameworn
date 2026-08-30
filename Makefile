SETTINGS ?= dev
FIXTURES = leagues game_types gear_types usage_types coa_types how_obtained_options externalresources teams season_sets auth_sources

ifeq ($(SETTINGS),dev)
  DJANGO_SETTINGS := gameworn.dev_settings
  VENV ?= ~/Development/gameworn/venv/bin/activate
else ifeq ($(SETTINGS),test)
  DJANGO_SETTINGS := gameworn.test_settings
  VENV ?=
else ifeq ($(SETTINGS),pa)
  DJANGO_SETTINGS := gameworn.pa_settings
  VENV ?=
else ifeq ($(SETTINGS),prod)
  DJANGO_SETTINGS := gameworn.settings
  VENV ?=
else
  $(error Unknown SETTINGS value '$(SETTINGS)'. Use dev, test, or prod)
endif

DJANGO_ENV := DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS)
VENV_CMD = $(if $(VENV),source $(VENV) &&,)

DB_FILE ?= db.sqlite3
BACKUP_DIR ?= backups

.PHONY: test test-e2e migrations migrate loadfixtures collectstatic run shell check tailwind backup restore deploy import_population_report export_population_report_data relay-tunnel

test:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py test memorabilia django_flowbite_widgets --exclude-tag=e2e

# Browser-driven regression tests (Playwright). Separate from `test` because
# they need browser binaries and a live server, not just SQLite - see
# requirements-e2e.txt. Run `pip install -r requirements-e2e.txt && python -m
# playwright install chromium` once before the first run.
# DJANGO_ALLOW_ASYNC_UNSAFE: Playwright's sync API drives its browser
# connection through a greenlet-switched asyncio loop on the main thread,
# which otherwise trips Django's ORM sync-safety check even though nothing
# here is actually running the ORM from async code.
test-e2e:
	$(VENV_CMD) DJANGO_ALLOW_ASYNC_UNSAFE=true $(DJANGO_ENV) python manage.py test memorabilia --tag=e2e

migrations:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py makemigrations

migrate:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py migrate

loadfixtures:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py loaddata $(FIXTURES)

collectstatic:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py collectstatic --noinput

run:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py runserver

shell:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py shell

# Expose the local dev server to Mailgun so inbound email replies relay locally.
# Starts a cloudflared tunnel + a temporary dev Mailgun route. Run `make run`
# in another terminal. Ctrl-C tears the route and tunnel back down.
relay-tunnel:
	bash scripts/relay_dev_tunnel.sh

check:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py check memorabilia

tailwind:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py tailwind build

backup:
	@mkdir -p $(BACKUP_DIR)
	@STAMP=$$(date +%Y%m%d_%H%M%S) && cp $(DB_FILE) $(BACKUP_DIR)/db_$$STAMP.sqlite3 && echo "Backed up to $(BACKUP_DIR)/db_$$STAMP.sqlite3"

restore:
	@if [ -n "$(FILE)" ]; then \
		cp $(FILE) $(DB_FILE) && echo "Restored from $(FILE)"; \
	else \
		LATEST=$$(ls -t $(BACKUP_DIR)/db_*.sqlite3 2>/dev/null | head -1); \
		if [ -z "$$LATEST" ]; then echo "No backups found in $(BACKUP_DIR)/"; exit 1; fi; \
		cp $$LATEST $(DB_FILE) && echo "Restored from $$LATEST"; \
	fi

import_population_report:
	@if [ -z "$(XLSX)" ]; then echo "Usage: make import_population_report XLSX=path/to/file.xlsx [SETTINGS=dev]"; exit 1; fi
	@BASENAME=$$(basename "$(XLSX)" .xlsx); \
	RAW_SEASON=$$(echo "$$BASENAME" | grep -oE '[0-9]{4}-[0-9]{2}' | head -1); \
	if [ -n "$$RAW_SEASON" ]; then \
		START_YEAR=$$(echo "$$RAW_SEASON" | cut -c1-4); \
		CENTURY=$$(echo "$$START_YEAR" | cut -c1-2); \
		SHORT_SUFFIX=$$(echo "$$RAW_SEASON" | grep -oE '[0-9]{2}$$'); \
		SUGGESTED_SEASON="$${START_YEAR}-$${CENTURY}$${SHORT_SUFFIX}"; \
	else \
		SUGGESTED_SEASON=""; \
	fi; \
	AFTER_SEASON=$$(echo "$$BASENAME" | sed "s/$$RAW_SEASON//"); \
	SUGGESTED_LEAGUE=$$(echo "$$AFTER_SEASON" | sed 's/[-_]/ /g; s/[Pp][Oo][Pp][Uu][Ll][Aa][Tt][Ii][Oo][Nn].*//' | xargs | tr '[:lower:]' '[:upper:]'); \
	SUGGESTED_LEAGUE=$${SUGGESTED_LEAGUE:-NHL}; \
	printf "Season [$$SUGGESTED_SEASON]: "; read SEASON; SEASON=$${SEASON:-$$SUGGESTED_SEASON}; \
	printf "League [$$SUGGESTED_LEAGUE]: "; read LEAGUE; LEAGUE=$${LEAGUE:-$$SUGGESTED_LEAGUE}; \
	printf "Import $$SEASON / $$LEAGUE from $(XLSX)? [y/N]: "; read CONFIRM; \
	if [ "$$CONFIRM" = "y" ] || [ "$$CONFIRM" = "Y" ]; then \
		$(VENV_CMD) $(DJANGO_ENV) python manage.py import_population_report "$(XLSX)" --season "$$SEASON" --league "$$LEAGUE"; \
	else \
		echo "Cancelled."; \
	fi

export_population_report_data:
	@if [ -z "$(SEASON)" ]; then echo "Usage: make export_population_report_data SEASON=2024-2025 [LEAGUE=NHL] [OUTPUT=file.json] [SETTINGS=dev]"; exit 1; fi
	$(VENV_CMD) $(DJANGO_ENV) python manage.py export_population_report_data --season "$(SEASON)" $(if $(LEAGUE),--league "$(LEAGUE)",) $(if $(OUTPUT),--output "$(OUTPUT)",)

deploy:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py migrate
	$(VENV_CMD) $(DJANGO_ENV) python manage.py loaddata $(FIXTURES)
	$(VENV_CMD) $(DJANGO_ENV) python manage.py collectstatic --noinput
