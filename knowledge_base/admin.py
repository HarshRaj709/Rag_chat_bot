from django.contrib import admin
from knowledge_base.models import KnowledgeBase, KBDocument

# Register your models here.
admin.site.register(KnowledgeBase)
admin.site.register(KBDocument)