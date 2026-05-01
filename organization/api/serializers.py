from rest_framework import serializers
from user.models import User
from organization.models import OrgInvite, OrgMembership, Organisation


# serializers.py
class OrgSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        user = self.context['request'].user
        qs = Organisation.objects.filter(name__iexact=value, created_by=user)

        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("An organization with this name already exists.")
        
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        return Organisation.create_with_owner(user=user, **validated_data)
    

class UpdateMemberRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgMembership
        fields = ("role",)

    def validate_role(self, value):
        if value == "owner":
            raise serializers.ValidationError("Cannot assign owner role directly.")
        return value


class OrgDetailSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True) #overriding to show username
    user_role = serializers.SerializerMethodField(read_only=True) #nested serializer to show user role
    members = serializers.SerializerMethodField(read_only=True) #nested serializer to show members

    class Meta:
        model = Organisation
        fields = ("id", "name", "created_by", "user_role", "members", "created_at", "updated_at")
        read_only_fields = ("id", "created_by", "user_role", "created_at", "updated_at")

    def get_user_role(self, obj):
        user = self.context['request'].user
        membership=OrgMembership.objects.filter(user=user, org=obj).first()
        return membership.role if membership else None
    
    def get_members(self, obj):
        return [
            {
                "id": member.user.id,
                "username": member.user.username,
                "email": member.user.email,
                "role": member.role
            }
            for member in obj.members.all()
        ]
    

#invites serializer
class OrgInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgInvite
        fields = ("id", "email", "role", "status", "expires_at", "created_at")
        read_only_fields = ("id", "status", "expires_at", "created_at")

    def validate_email(self, value):
        request = self.context["request"]
        org = self.context["org"]

        existing_user = User.objects.filter(email=value).first()
        if existing_user:
            if OrgMembership.objects.filter(user=existing_user, org=org).exists():
                raise serializers.ValidationError("This user is already a member of the organisation.")

        if OrgInvite.objects.filter(org=org, email=value, status="pending").exists():
            raise serializers.ValidationError("A pending invite already exists for this email.")

        return value

    def create(self, validated_data):
        org = self.context["org"]
        invited_by = self.context["request"].user
        return OrgInvite.objects.create(
            org=org,
            invited_by=invited_by,
            **validated_data
        )


class OrgInviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            invite = OrgInvite.objects.select_related("org").get(
                token=value, status="pending"
            )
        except OrgInvite.DoesNotExist:
            raise serializers.ValidationError("Invalid or already used invite token.")

        if invite.is_expired():
            invite.status = "expired"
            invite.save(update_fields=["status"])
            raise serializers.ValidationError("This invite has expired.")

        self.context["invite"] = invite  # pass to view cleanly
        return value