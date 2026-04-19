VENV := source ~/Development/gameworn/venv/bin/activate
SETTINGS ?= dev
FIXTURES = leagues game_types gear_types usage_types loa_types how_obtained_options externalresources teams season_sets auth_sources

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

.PHONY: test migrations migrate loadfixtures collectstatic run shell check tailwind

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

import_population_report:
	$(VENV) && $(DJANGO_ENV) python manage.py import_population_report $(XLSX) --season $(SEASON)

deploy:
	python manage.py loaddata $(FIXTURES)
	python manage.py migrate
