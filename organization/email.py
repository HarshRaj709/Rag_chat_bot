from django.conf import settings
from django.core.mail import send_mail
from django.utils.html import strip_tags

def send_invite_email(invite):
    invite_link = f"{settings.FRONTEND_URL}/invites/accept/?token={invite.token}"

    role_colors = {
        "owner": ("#ede9fe", "#6d28d9"),
        "admin": ("#dbeafe", "#1d4ed8"),
        "member": ("#f1f5f9", "#64748b"),
    }
    bg, fg = role_colors.get(invite.role.lower(), ("#f1f5f9", "#64748b"))

    html = f"""
    <div style="background:#f8fafc;padding:32px 16px;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;">
      <div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;text-align:center;">
          <div style="font-size:20px;font-weight:800;color:#ffffff;">RAG SaaS</div>
          <div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:4px;">Turn your documents into an intelligent chatbot</div>
        </div>
        <div style="padding:32px;">
          <span style="display:inline-block;font-size:12px;font-weight:600;padding:3px 12px;border-radius:99px;background:#ede9fe;color:#6d28d9;">✨ Team Invite</span>
          <h2 style="color:#0f172a;font-size:20px;margin:16px 0 8px;">You're invited to join {invite.org.name}</h2>
          <p style="color:#64748b;font-size:14px;line-height:1.6;margin:0;">
            Hi there,<br><b style="color:#0f172a;">{invite.invited_by.username}</b> has invited you to join
            <b style="color:#0f172a;">{invite.org.name}</b> as
            <span style="display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:99px;background:{bg};color:{fg};">{invite.role.upper()}</span>
          </p>
          <div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:20px 0;font-size:13px;color:#64748b;">
            🏢 <b style="color:#0f172a;">{invite.org.name}</b> · Shared knowledge bases, bots &amp; grounded answers<br>
            ⏳ Link expires in <b style="color:#0f172a;">2 days</b>
          </div>
          <a href="{invite_link}" style="display:block;text-align:center;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#ffffff;font-weight:600;font-size:15px;padding:14px 28px;border-radius:10px;text-decoration:none;">Accept Invite →</a>
          <p style="font-size:12px;color:#64748b;margin:16px 0 0;word-break:break-all;">Button not working? Paste this link:<br><a href="{invite_link}" style="color:#6366f1;">{invite_link}</a></p>
          <p style="font-size:12px;color:#64748b;margin-top:16px;">If you didn't expect this invite, you can safely ignore this email.</p>
        </div>
        <div style="border-top:1px solid #e2e8f0;padding:16px 32px;text-align:center;font-size:12px;color:#64748b;">
          © 2026 RAG SaaS · Built for grounded AI support
        </div>
      </div>
    </div>
    """.strip()

    text = f"""Hi,
        {invite.invited_by.username} has invited you to join {invite.org.name} as {invite.role}.
        Accept (expires in 2 days): {invite_link}
        If you didn't expect this invite, you can ignore this email."""

    send_mail(
        subject=f"You're invited to join {invite.org.name}",
        message=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invite.email],
        html_message=html,
        fail_silently=False,
    )