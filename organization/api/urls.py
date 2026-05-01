from django.urls import path
from .views import (
    DeleteOrganizationView,
    OrgDetailView,
    OrgInviteAcceptView,
    OrgInviteListCreateView,
    OrgListView,
    OrgCreateView,
    OrgInviteCancelView,
    OrgUpdateView,
    RemoveMemberView,
    UpdateMemberRoleView,
)


urlpatterns = [
    path("orgs/", OrgListView.as_view(), name="org-list"),
    path("orgs/create/", OrgCreateView.as_view(), name="org-create"),
    path("orgs/<uuid:pk>/", OrgDetailView.as_view(), name="org-detail"),
    path("orgs/<uuid:pk>/delete/", DeleteOrganizationView.as_view(), name="org-delete"),
    path("orgs/<uuid:pk>/update/", OrgUpdateView.as_view(), name="org-update"),
    path("orgs/<uuid:pk>/members/remove/<uuid:user_id>/", RemoveMemberView.as_view(), name="org-remove-member"),
    path("orgs/<uuid:pk>/members/update/<uuid:user_id>/", UpdateMemberRoleView.as_view(), name="org-update-member-role"),
    
    # invites
    path("orgs/<uuid:pk>/invites/", OrgInviteListCreateView.as_view(), name="org-invites"),
    path("orgs/<uuid:pk>/invites/<uuid:invite_pk>/", OrgInviteCancelView.as_view(), name="org-invite-cancel"),
    path("invites/accept/", OrgInviteAcceptView.as_view(), name="invite-accept"),
]
