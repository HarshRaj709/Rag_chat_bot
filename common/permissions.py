from rest_framework.permissions import BasePermission
from organization.models import OrgMembership


def get_cached_membership(request, org_pk, roles=None):
    """Membership lookup cached per request.

    Every org-scoped endpoint previously hit the DB 2-3 times for the
    same (user, org) membership row: once in ``has_permission``, again
    in ``has_object_permission``, and again via ``GetOrgMixin.get_org``
    callers / serializers. Over a cross-region link (Supabase pooler)
    each round-trip costs ~150-250ms, so de-duplicating them saves
    ~0.5s per request. The cache lives on the request object, so it is
    scoped to a single API call and never goes stale across requests.
    """
    if not request.user or not request.user.is_authenticated:
        return None
    cache = getattr(request, "_org_membership_cache", None)
    if cache is None:
        cache = {}
        request._org_membership_cache = cache
    key = (str(org_pk), tuple(roles) if roles else None)
    if key not in cache:
        qs = OrgMembership.objects.filter(user=request.user, org_id=org_pk)
        if roles:
            qs = qs.filter(role__in=roles)
        cache[key] = qs.first()
    return cache[key]


class IsOrgMember(BasePermission):

    # ── called for EVERY request (list, create, retrieve, update, delete)
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org_pk = view.kwargs.get("pk")
        if org_pk:
            return get_cached_membership(request, org_pk) is not None
        return True

    # ── called only for retrieve, update, delete (when get_object() runs)
    def has_object_permission(self, request, view, obj):
        org = obj if hasattr(obj, "members") else obj.org
        return get_cached_membership(request, org.pk) is not None


class IsOrgAdmin(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        org_pk = view.kwargs.get("pk")
        if org_pk:
            return (
                get_cached_membership(request, org_pk, roles=["admin", "owner"])
                is not None
            )

        return True

    def has_object_permission(self, request, view, obj):
        org = obj if hasattr(obj, "members") else obj.org
        return (
            get_cached_membership(request, org.pk, roles=["admin", "owner"])
            is not None
        )