# organization/emails.py
from django.core.mail import send_mail
from django.conf import settings


def send_invite_email(invite):
    invite_link = f"http://localhost:8000/api/invites/accept/?token={invite.token}"     #f"{settings.FRONTEND_URL}/invites/accept/?token={invite.token}"
    
    send_mail(
        subject=f"You're invited to join {invite.org.name}",
        message=f"""
                Hi,{invite.invited_by.username} has invited you to join {invite.org.name} as a {invite.role}.
                Click the link below to accept the invite (expires in 2 days):
                {invite_link}
                If you didn't expect this invite, you can ignore this email.""".strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invite.email],
        fail_silently=False,
)