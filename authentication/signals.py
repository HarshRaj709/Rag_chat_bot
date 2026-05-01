from django.db.models.signals import post_save
from django.dispatch import receiver
from user.models import User
from organization.models import Organisation, OrgMembership

@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    
    org = Organisation.objects.create(name=f"{instance.username}_organization", created_by=instance)
    OrgMembership.objects.create(user=instance, org=org, role="owner")
