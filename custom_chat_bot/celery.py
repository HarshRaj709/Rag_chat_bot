import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "custom_chat_bot.settings") #Load my Django settings from custom_chat_bot.settings.

app = Celery("custom_chat_bot")
app.config_from_object("django.conf:settings", namespace="CELERY") #This tells Celery to read settings from Django's settings.py.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)  #test
def debug_task(self):
    print(f"Request: {self.request!r}")
