from django.db import models
from datetime import timedelta
from django.utils import timezone
import secrets
from user.models import User
from common.models import BaseModel
from django.db import transaction
from django.db.models.functions import Lower

ROLE_CHOICES = [
    ("owner", "owner"),
    ("admin", "Admin"),
    ("member", "Member")
]

STATUS = [
    ("pending", "Pending"),
    ("accepted", "Accepted"),
    ("expired", "Expired")
]


class Organisation(BaseModel):
    name = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="owned_orgs"
    )

    def __str__(self):
        return self.name
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "created_by",
                name="unique_org_per_user_case_insensitive"
            )
        ]
    
    @classmethod
    def create_with_owner(cls, user, **data):
        with transaction.atomic():            
            org = cls.objects.create(**data, created_by=user)
            OrgMembership.objects.create(
                user=user,
                org=org,
                role="owner"
            )
            return org

class OrgMembership(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "org"], name="unique_membership")
        ]

    def __str__(self):
        return f"{self.user.username} in {self.org.name}"
    

class OrgInvite(BaseModel):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="invites")
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default="member"
    )
    token = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "email"],
                condition=models.Q(status="pending"),
                name="unique_pending_invite"
            )
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=2)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at