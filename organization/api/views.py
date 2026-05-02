from rest_framework.response import Response
from rest_framework.generics import ListAPIView, UpdateAPIView, CreateAPIView, DestroyAPIView, RetrieveAPIView, GenericAPIView
from organization.email import send_invite_email
from organization.models import Organisation, OrgMembership, OrgInvite
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsOrgAdmin, IsOrgMember
from common.mixins import GetOrgMixin
from .serializers import OrgSerializer, OrgDetailSerializer, OrgInviteSerializer, OrgInviteAcceptSerializer, UpdateMemberRoleSerializer
from django.shortcuts import get_object_or_404 
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from django.db import transaction


class OrgListView(ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = OrgSerializer
    
    def get_queryset(self):
        return Organisation.objects.filter(members__user=self.request.user)
    

class OrgCreateView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrgSerializer

    def perform_create(self, serializer):
        serializer.save()


class OrgDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = OrgDetailSerializer

    def get_queryset(self):
        return Organisation.objects.filter(
            members__user=self.request.user
        ).prefetch_related("members")


class DeleteOrganizationView(DestroyAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    queryset = Organisation.objects.all()

    # def get_queryset(self):
    #     return Organisation.objects.filter(
    #         members__user=self.request.user,
    #         members__role="owner",
    #     )

class OrgUpdateView(UpdateAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = OrgSerializer
    http_method_names = ["patch"]

    def get_queryset(self):
        return Organisation.objects.filter(             #to check what user can see
            members__user=self.request.user,
            members__role__in=["admin", "owner"]
        )
    

class RemoveMemberView(DestroyAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def get_object(self):
        org = get_object_or_404(
            Organisation,
            pk=self.kwargs["pk"],
            members__user=self.request.user,        # requester must be a member
            members__role__in=["admin", "owner"]    # requester must be admin/owner
            )
        
        membership =  get_object_or_404(
            OrgMembership,
            user=self.kwargs["user_id"],
            org=org
        )

        if membership.role == "owner":
            raise PermissionDenied("Cannot remove the owner of the organization.")
        
        if membership.user == self.request.user:
            raise PermissionDenied("You cannot remove yourself from the organization.")
        
        return membership

    def perform_destroy(self, instance):
        instance.delete()


class UpdateMemberRoleView(UpdateAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = UpdateMemberRoleSerializer
    http_method_names = ["patch"]

    def get_object(self):
        org = get_object_or_404(
            Organisation,
            id = self.kwargs["pk"],
            members__user=self.request.user,
            members__role__in=["admin", "owner"]

        )

        membership = get_object_or_404(
            OrgMembership,
            user_id=self.kwargs["user_id"],
            org=org
        )

        if membership.role == "owner":
            raise PermissionDenied("Owner role cannot be changed.")

        if membership.user == self.request.user:
            return PermissionDenied("You cannot change your own role")

        return membership



#Organization invites views
class OrgInviteListCreateView(GetOrgMixin, ListAPIView, CreateAPIView):
    """
    GET  /orgs/<pk>/invites/   — list all pending invites for this org
    POST /orgs/<pk>/invites/   — send a new invite
    Only org admins and owners can invite.
    """
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = OrgInviteSerializer

    def get_serializer_context(self):
        # inject org into serializer context so serializer.validate_email can use it
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return OrgInvite.objects.filter(
            org=self.get_org(), status="pending"
        ).select_related("invited_by")

    def perform_create(self, serializer):
        invite = serializer.save()
        # send email after the invite row is safely committed
        send_invite_email(invite)

    # ListAPIView uses get(), CreateAPIView uses post()
    # combining both in one view means one URL handles both methods cleanly
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class OrgInviteCancelView(DestroyAPIView):
    """
    DELETE /orgs/<pk>/invites/<invite_pk>/
    Cancel a pending invite — soft delete by setting status to expired.
    Only admins and owners can cancel.
    """
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def get_object(self):
        org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return get_object_or_404(
            OrgInvite,
            pk=self.kwargs["invite_pk"],
            org=org,
            status="pending"  # can only cancel pending invites
        )

    def perform_destroy(self, instance):
        # soft delete — keep the record, just mark it expired
        instance.status = "expired"
        instance.save(update_fields=["status"])
    

class OrgInviteAcceptView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrgInviteAcceptSerializer

    def post(self, request):
        # get_serializer automatically passes context (request, view, format)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite = serializer.context["invite"]
        user = request.user

        with transaction.atomic():

            membership, created = OrgMembership.objects.get_or_create(
                user=user,
                org=invite.org,
                defaults={"role": invite.role}
            )

            if not created:
                return Response(
                    {"detail": "You are already a member of this organisation."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            invite.status = "accepted"
            invite.save(update_fields=["status"])

        return Response({
            "detail": f"You have joined {invite.org.name} as {invite.role}.",
            "org_id": str(invite.org.id),
        }, status=status.HTTP_200_OK)