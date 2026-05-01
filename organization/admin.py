from django.contrib import admin
from .models import Organisation, OrgMembership, OrgInvite

# Register your models here.
admin.site.register(Organisation)
admin.site.register(OrgMembership)
admin.site.register(OrgInvite)