# organization/tasks.py
"""Background email jobs — never block the request on SMTP."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="organization.send_invite_email",
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def send_invite_email_task(self, invite_id: str) -> dict:
    from organization.models import OrgInvite

    try:
        invite = OrgInvite.objects.select_related("org", "invited_by").get(pk=invite_id)
    except OrgInvite.DoesNotExist:
        logger.warning("send_invite_email_task: invite %s gone, skipping", invite_id)
        return {"ok": False, "reason": "invite-not-found"}

    if invite.status != "pending":
        return {"ok": True, "reason": f"invite-{invite.status}-skipped"}

    try:
        # Lazy import keeps worker boot light and mockable in tests.
        from organization.email import send_invite_email

        send_invite_email(invite)
        logger.info("Invite email sent to %s (org=%s)", invite.email, invite.org_id)
        return {"ok": True}
    except Exception:
        # Last retry exhausted -> surface as `failed` so FE can show Resend.
        if self.request.retries >= self.max_retries:
            invite.status = "failed"
            invite.save(update_fields=["status"])
            logger.exception("Invite email permanently failed for %s", invite.email)
            return {"ok": False, "reason": "smtp-failed"}
        raise
