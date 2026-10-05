#!/usr/bin/env bash
set -e

echo "Starting Celery..."

pipenv run celery -A custom_chat_bot worker -l info --concurrency=1 &

echo "Starting Django..."

exec pipenv run gunicorn custom_chat_bot.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT}