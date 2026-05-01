from rest_framework.permissions import BasePermission
from organization.models import OrgMembership


class IsOrgMember(BasePermission):

    # ── called for EVERY request (list, create, retrieve, update, delete)
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org_pk = view.kwargs.get("pk")
        if org_pk:
            return OrgMembership.objects.filter(
                user=request.user, org_id=org_pk
            ).exists()
        return True

    # ── called only for retrieve, update, delete (when get_object() runs)
    def has_object_permission(self, request, view, obj):
        org = obj if hasattr(obj, "members") else obj.org
        return OrgMembership.objects.filter(
            user=request.user, org=org
        ).exists()


class IsOrgAdmin(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        org_pk = view.kwargs.get("pk")
        if org_pk:
            return OrgMembership.objects.filter(
                user=request.user, org_id=org_pk, role__in=["admin", "owner"]
            ).exists()

        return True

    def has_object_permission(self, request, view, obj):
        org = obj if hasattr(obj, "members") else obj.org
        return OrgMembership.objects.filter(
            user=request.user, org=org, role__in=["admin", "owner"]
        ).exists()