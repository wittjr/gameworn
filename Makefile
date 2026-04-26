VENV ?= source ~/Development/gameworn/venv/bin/activate
SETTINGS ?= dev
FIXTURES = leagues game_types gear_types usage_types coa_types how_obtained_options externalresources teams season_sets auth_sources

ifeq ($(SETTINGS),dev)
  DJANGO_SETTINGS := gameworn.dev_settings
else ifeq ($(SETTINGS),test)
  DJANGO_SETTINGS := gameworn.test_settings
else ifeq ($(SETTINGS),prod)
  DJANGO_SETTINGS := gameworn.settings
else
  $(error Unknown SETTINGS value '$(SETTINGS)'. Use dev, test, or prod)
endif

DJANGO_ENV := DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS)

DB_FILE ?= db.sqlite3
BACKUP_DIR ?= backups

.PHONY: test migrations migrate loadfixtures collectstatic run shell check tailwind backup restore

test:
	$(VENV) && $(DJANGO_ENV) python manage.py test memorabilia

migrations:
	$(VENV) && $(DJANGO_ENV) python manage.py makemigrations

migrate:
	$(VENV) && $(DJANGO_ENV) python manage.py migrate

loadfixtures:
	$(VENV) && $(DJANGO_ENV) python manage.py loaddata $(FIXTURES)

collectstatic:
	$(VENV) && $(DJANGO_ENV) python manage.py collectstatic --noinput

run:
	$(VENV) && $(DJANGO_ENV) python manage.py runserver

shell:
	$(VENV) && $(DJANGO_ENV) python manage.py shell

check:
	$(VENV) && $(DJANGO_ENV) python manage.py check memorabilia

tailwind:
	$(VENV) && $(DJANGO_ENV) python manage.py tailwind build

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
	$(VENV) && $(DJANGO_ENV) python manage.py import_population_report $(XLSX) --season $(SEASON)

deploy:
	python manage.py loaddata $(FIXTURES)
	python manage.py migrate
