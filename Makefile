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

.PHONY: test migrations migrate loadfixtures collectstatic run shell check tailwind backup restore deploy

test:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py test memorabilia

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
	$(VENV_CMD) $(DJANGO_ENV) python manage.py import_population_report $(XLSX) --season $(SEASON)

deploy:
	$(VENV_CMD) $(DJANGO_ENV) python manage.py migrate
	$(VENV_CMD) $(DJANGO_ENV) python manage.py loaddata $(FIXTURES)
