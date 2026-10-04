#!/usr/bin/env bash
set -e

pip install pipenv
pipenv install --deploy
pipenv run python manage.py migrate
pipenv run python manage.py collectstatic --no-input