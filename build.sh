#!/usr/bin/env bash
set -e

pipenv install --deploy
pipenv run python manage.py migrate
pipenv run python manage.py collectstatic --no-input