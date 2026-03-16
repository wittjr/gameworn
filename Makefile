VENV := source ~/Development/gameworn/venv/bin/activate
DEV_SETTINGS := DJANGO_SETTINGS_MODULE=gameworn.dev_settings

.PHONY: test migrations migrate run shell

test:
	$(VENV) && $(DEV_SETTINGS) python manage.py test memorabilia

migrations:
	$(VENV) && $(DEV_SETTINGS) python manage.py makemigrations

migrate:
	$(VENV) && python manage.py migrate

collectstatic:
	$(VENV) && $(DEV_SETTINGS) python manage.py collectstatic --noinput

run:
	$(VENV) && python manage.py runserver

shell:
	$(VENV) && python manage.py shell
