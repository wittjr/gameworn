#!/bin/bash
python manage.py migrate --no-input
python -m gunicorn --bind=0.0.0.0 --timeout 600 -w 3 gameworn.wsgi
