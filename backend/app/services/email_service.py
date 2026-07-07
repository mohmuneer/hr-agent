"""إرسال إشعارات البريد الإلكتروني للمرشحين."""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_smtp_config() -> dict:
    s = get_settings()
    return {
        "host": s.SMTP_HOST,
        "port": s.SMTP_PORT,
        "user": s.SMTP_USER,
        "password": s.SMTP_PASSWORD,
        "from_addr": s.SMTP_FROM,
    }


def send_email(to: str, subject: str, body: str) -> bool:
    cfg = _get_smtp_config()
    if not cfg["host"] or not cfg["user"]:
        logger.warning("SMTP not configured — skipping email to %s", to)
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"] or cfg["user"]
    msg["To"] = to

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        logger.info("Email sent to %s", to)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


def send_status_notification(to: str, name: str, status: str, detail: str | None = None) -> bool:
    status_map = {
        "approved": "تمت الموافقة على طلبك",
        "rejected": "تم الاعتذار عن طلبك",
        "accepted": "تم قبولك نهائيًا",
    }
    subject = status_map.get(status, "تحديث حالة طلب التوظيف")

    lines = [f"السلام عليكم {name}،", ""]
    if status == "approved":
        lines.append("يسرنا إبلاغك أنه تمت الموافقة على طلب التقديم الخاص بك.")
        if detail:
            lines.append(f"")
            lines.append(f"موعد المقابلة: {detail}")
        lines.append("")
        lines.append("يمكنك الدخول إلى رابط المقابلة الصوتية من صفحة التحقق من حالة الطلب.")
    elif status == "rejected":
        lines.append("نشكر لك اهتمامك، ونأسف لإعلامك أنه تم الاعتذار عن طلبك.")
        if detail:
            lines.append(f"")
            lines.append(f"ملاحظات: {detail}")
    elif status == "accepted":
        lines.append("نهنئك بقبولك النهائي! سيتم التواصل معك قريبًا بخصوص الخطوات التالية.")
        if detail:
            lines.append(f"")
            lines.append(f"ملاحظات: {detail}")
    else:
        lines.append(f"تم تحديث حالة طلبك إلى: {status}")

    lines.append("")
    lines.append("للاستفسار، يرجى التواصل مع فريق الموارد البشرية.")
    body = "\n".join(lines)

    return send_email(to, subject, body)
