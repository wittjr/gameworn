VENV := source ~/Development/gameworn/venv/bin/activate
TEST_SETTINGS := DJANGO_SETTINGS_MODULE=gameworn.test_settings

.PHONY: test migrations migrate run shell

test:
	$(VENV) && $(TEST_SETTINGS) python manage.py test memorabilia

migrations:
	$(VENV) && $(TEST_SETTINGS) python manage.py makemigrations

migrate:
	$(VENV) && python manage.py migrate

collectstatic:
	$(VENV) && $(TEST_SETTINGS) python manage.py collectstatic --noinput

run:
	$(VENV) && python manage.py runserver

shell:
	$(VENV) && python manage.py shell
