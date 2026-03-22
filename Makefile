VENV := source ~/Development/gameworn/venv/bin/activate
DEV_SETTINGS := DJANGO_SETTINGS_MODULE=gameworn.dev_settings

.PHONY: test migrations migrate loadfixtures run shell

test:
	$(VENV) && $(DEV_SETTINGS) python manage.py test memorabilia

migrations:
	$(VENV) && $(DEV_SETTINGS) python manage.py makemigrations

migrate:
	$(VENV) && $(DEV_SETTINGS) python manage.py migrate

loadfixtures:
	$(VENV) && $(DEV_SETTINGS) python manage.py loaddata leagues game_types usage_types loa_types how_obtained_options

collectstatic:
	$(VENV) && $(DEV_SETTINGS) python manage.py collectstatic --noinput

run:
	$(VENV) && $(DEV_SETTINGS) python manage.py runserver

shell:
	$(VENV) && $(DEV_SETTINGS) python manage.py shell
