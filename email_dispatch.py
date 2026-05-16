"""
job_hunter/email_dispatch.py

Email dispatch layer — supports SMTP (Gmail/custom) and SendGrid.
Used for:
  • Review notifications  — "Your application package is ready for review"
  • Dispatch confirmations — "Application sent to employer"
  • n8n trigger emails    — machine-readable metadata for automation

Configure via .env:
  EMAIL_PROVIDER=smtp | sendgrid
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM
  SENDGRID_API_KEY / SENDGRID_FROM
  REVIEW_RECIPIENT_EMAIL   — where review emails go (usually the user themselves)
"""

import os, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger(__name__)

PROVIDER            = os.getenv("EMAIL_PROVIDER", "smtp").lower()
SMTP_HOST           = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT           = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER           = os.getenv("SMTP_USER", "")
SMTP_PASS           = os.getenv("SMTP_PASS", "")
SMTP_FROM           = os.getenv("SMTP_FROM", SMTP_USER)
SENDGRID_API_KEY    = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM       = os.getenv("SENDGRID_FROM", "")
REVIEW_EMAIL        = os.getenv("REVIEW_RECIPIENT_EMAIL", "")
API_BASE_URL        = os.getenv("API_BASE_URL", "http://localhost:5055")


# ════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL SEND
# ════════════════════════════════════════════════════════════════════════════
def _send_smtp(to: str, subject: str, html: str,
               text: str = "", attachments: Optional[list] = None) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        log.warning("SMTP not configured — email skipped")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_FROM
        msg["To"]      = to
        if text:
            msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        if attachments:
            for name, data in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{name}"')
                msg.attach(part)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(SMTP_FROM, to, msg.as_string())
        return True
    except Exception as e:
        log.error(f"SMTP send error: {e}")
        return False


def _send_sendgrid(to: str, subject: str, html: str,
                   text: str = "", attachments: Optional[list] = None) -> bool:
    if not SENDGRID_API_KEY:
        log.warning("SendGrid not configured — email skipped")
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        import base64

        mail = Mail(
            from_email=SENDGRID_FROM,
            to_emails=to,
            subject=subject,
            html_content=html,
        )
        if text:
            mail.plain_text_content = text
        if attachments:
            for name, data in attachments:
                att = Attachment(
                    FileContent(base64.b64encode(data).decode()),
                    FileName(name),
                    FileType("application/octet-stream"),
                    Disposition("attachment"),
                )
                mail.attachment = att
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        resp = sg.send(mail)
        return resp.status_code in (200, 202)
    except Exception as e:
        log.error(f"SendGrid send error: {e}")
        return False


def send_email(to: str, subject: str, html: str,
               text: str = "", attachments: Optional[list] = None) -> bool:
    if not to:
        log.warning("No recipient — email skipped")
        return False
    if PROVIDER == "sendgrid":
        return _send_sendgrid(to, subject, html, text, attachments)
    return _send_smtp(to, subject, html, text, attachments)


# ════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL TEMPLATES
# ════════════════════════════════════════════════════════════════════════════
def _job_meta_table(job: dict) -> str:
    rows = [
        ("Role",     job.get("title", "—")),
        ("Company",  job.get("company", "—")),
        ("Location", job.get("location", "—")),
        ("Deadline", job.get("deadline", "TBC")),
        ("Source",   job.get("source",   "—")),
        ("Match",    f"{job.get('match_score', '?')}%"),
    ]
    return "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#888;white-space:nowrap'><b>{k}</b></td>"
        f"<td style='padding:4px 0'>{v}</td></tr>"
        for k, v in rows
    )


def _scholarship_meta_table(s: dict) -> str:
    rows = [
        ("Scholarship", s.get("title", "—")),
        ("Funder",      s.get("funder", s.get("company", "—"))),
        ("Country",     s.get("funder_country", "—")),
        ("Level",       s.get("level", "—")),
        ("Funding",     (s.get("funding_type") or "—").replace("_", " ").title()),
        ("Deadline",    s.get("deadline", "TBC")),
        ("Match",       f"{s.get('match_score', '?')}%"),
    ]
    return "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#888;white-space:nowrap'><b>{k}</b></td>"
        f"<td style='padding:4px 0'>{v}</td></tr>"
        for k, v in rows
    )


def _base_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:Arial,sans-serif;color:#222;max-width:680px;margin:0 auto;padding:24px">
  <div style="background:#1a73e8;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0">Job Hunter KE</h2>
    <p  style="margin:4px 0 0;opacity:.85;font-size:14px">{title}</p>
  </div>
  <div style="border:1px solid #e0e0e0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    {body}
  </div>
  <p style="color:#aaa;font-size:12px;margin-top:16px;text-align:center">
    Job Hunter KE · Automated application assistant
  </p>
</body>
</html>"""


def notify_review_ready(record: dict, record_type: str = "job",
                        recipient: Optional[str] = None) -> bool:
    """Send a 'ready for review' notification email to the user."""
    to = recipient or REVIEW_EMAIL
    if not to:
        log.warning("notify_review_ready: no recipient configured")
        return False

    rec_id  = record.get("id", "")
    is_schol = record_type == "scholarship"
    path     = "scholarships" if is_schol else "jobs"
    title    = record.get("title", "New Application")
    company  = record.get("funder", record.get("company", ""))
    score    = record.get("match_score", "?")

    approve_url = f"{API_BASE_URL}/{path}/{rec_id}/approve"
    reject_url  = f"{API_BASE_URL}/{path}/{rec_id}/reject"

    meta_table = _scholarship_meta_table(record) if is_schol else _job_meta_table(record)
    doc_label  = "Motivation Letter" if is_schol else "Cover Letter"
    doc_field  = "motivation_letter" if is_schol else "cover_letter"
    doc_preview = (record.get(doc_field) or "")[:800].replace("\n", "<br>")

    subject = f"[Review] {title} @ {company} — Match {score}%"

    body = f"""
    <p>Your AI-generated application package is ready for review.</p>

    <table style="margin-bottom:20px">{meta_table}</table>

    <h3 style="border-bottom:1px solid #eee;padding-bottom:8px">{doc_label} Preview</h3>
    <div style="background:#f9f9f9;padding:16px;border-radius:4px;font-size:14px;line-height:1.6">
      {doc_preview}…
    </div>

    <div style="margin-top:24px;display:flex;gap:12px">
      <a href="{approve_url}" style="background:#34a853;color:#fff;padding:10px 24px;
         border-radius:4px;text-decoration:none;font-weight:bold">✓ Approve</a>
      &nbsp;&nbsp;
      <a href="{reject_url}" style="background:#ea4335;color:#fff;padding:10px 24px;
         border-radius:4px;text-decoration:none;font-weight:bold">✗ Reject</a>
    </div>

    <p style="margin-top:20px;color:#666;font-size:13px">
      Or open your <a href="{API_BASE_URL}/dashboard">dashboard</a> to review and edit documents.
    </p>

    <!-- n8n metadata (machine-readable) -->
    <!-- JOB_HUNTER_META: {{"id":"{rec_id}","type":"{record_type}","action":"review","score":{score}}} -->
    """

    return send_email(to, subject, _base_html(subject, body))


def notify_dispatched(record: dict, record_type: str = "job",
                      recipient: Optional[str] = None) -> bool:
    """Confirmation email after an application has been dispatched."""
    to = recipient or REVIEW_EMAIL
    if not to:
        return False

    is_schol = record_type == "scholarship"
    title    = record.get("title", "Application")
    company  = record.get("funder", record.get("company", ""))
    url      = record.get("url", "#")

    subject = f"[Dispatched] {title} @ {company}"
    body = f"""
    <p>Your application for <b>{title}</b> at <b>{company}</b> has been dispatched.</p>
    <p><a href="{url}">View original posting</a></p>
    <p style="color:#666;font-size:13px">Track your applications in the
    <a href="{API_BASE_URL}/dashboard">dashboard</a>.</p>
    """
    return send_email(to, subject, _base_html(subject, body))


def notify_reminder_digest(
    expiring_jobs: list,
    expiring_schols: list,
    stale_jobs: list,
    stale_schols: list,
    recipient: Optional[str] = None,
    deadline_days: int = 7,
) -> bool:
    """
    Daily digest email. Groups items by urgency:
      • Deadlines closing within deadline_days days
      • Approved items sitting unsubmitted for 48+ hours
    """
    to = recipient or REVIEW_EMAIL
    if not to:
        log.warning("notify_reminder_digest: no recipient configured")
        return False

    total = len(expiring_jobs) + len(expiring_schols) + len(stale_jobs) + len(stale_schols)
    if total == 0:
        log.info("Reminder digest: nothing to report, skipping email")
        return True  # not an error — just nothing to send

    def _urgency_color(days_left):
        if days_left is None: return "#888"
        if days_left <= 1:    return "#dc2626"  # red — today/tomorrow
        if days_left <= 3:    return "#ea580c"  # orange — very soon
        return "#ca8a04"                         # amber — this week

    def _days_label(days_left):
        if days_left is None: return "Unknown deadline"
        if days_left == 0:    return "⚠ Due TODAY"
        if days_left == 1:    return "⚠ Due TOMORROW"
        return f"{days_left} days left"

    def _item_row(item, is_schol=False):
        title    = item.get("title", "—")
        company  = item.get("funder", item.get("company", "—"))
        deadline = item.get("deadline", "—")
        status   = item.get("status", "—").replace("_", " ").title()
        days     = item.get("days_left")
        color    = _urgency_color(days)
        label    = _days_label(days)
        path     = "scholarships" if is_schol else "jobs"
        url      = f"{API_BASE_URL}/{path}?status={item.get('status','pending')}"
        return f"""
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:10px 12px">
            <a href="{url}" style="font-weight:600;color:#1a1a1a;text-decoration:none">{title}</a>
            <div style="font-size:12px;color:#888;margin-top:2px">{company}</div>
          </td>
          <td style="padding:10px 12px;font-size:12px;color:#555">{status}</td>
          <td style="padding:10px 12px;font-size:12px;color:#555">{deadline}</td>
          <td style="padding:10px 12px;font-size:12px;font-weight:600;color:{color};white-space:nowrap">{label}</td>
        </tr>"""

    def _stale_row(item, is_schol=False):
        title   = item.get("title", "—")
        company = item.get("funder", item.get("company", "—"))
        path    = "scholarships" if is_schol else "jobs"
        url     = f"{API_BASE_URL}/{path}?status=approved"
        return f"""
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:10px 12px">
            <a href="{url}" style="font-weight:600;color:#1a1a1a;text-decoration:none">{title}</a>
            <div style="font-size:12px;color:#888;margin-top:2px">{company}</div>
          </td>
          <td colspan="3" style="padding:10px 12px;font-size:12px;color:#ea580c;font-weight:600">
            Approved but not yet submitted — take action
          </td>
        </tr>"""

    def _section(title, rows_html, color="#6d28d9"):
        if not rows_html:
            return ""
        return f"""
        <div style="margin-bottom:28px">
          <h3 style="margin:0 0 12px;font-size:14px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:.5px">{title}</h3>
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="background:#f9f9fb">
                <th style="padding:8px 12px;text-align:left;color:#555;font-weight:600">Title</th>
                <th style="padding:8px 12px;text-align:left;color:#555;font-weight:600">Status</th>
                <th style="padding:8px 12px;text-align:left;color:#555;font-weight:600">Deadline</th>
                <th style="padding:8px 12px;text-align:left;color:#555;font-weight:600">Urgency</th>
              </tr>
            </thead>
            <tbody>{"".join(rows_html)}</tbody>
          </table>
        </div>"""

    sections = ""
    if expiring_jobs:
        sections += _section(
            f"⏰ Job Deadlines Within {deadline_days} Days ({len(expiring_jobs)})",
            [_item_row(j) for j in expiring_jobs], "#dc2626"
        )
    if expiring_schols:
        sections += _section(
            f"🎓 Scholarship Deadlines Within {deadline_days} Days ({len(expiring_schols)})",
            [_item_row(s, is_schol=True) for s in expiring_schols], "#7c3aed"
        )
    if stale_jobs or stale_schols:
        stale_rows = [_stale_row(j) for j in stale_jobs] + \
                     [_stale_row(s, is_schol=True) for s in stale_schols]
        sections += _section(
            f"⚠ Approved But Unsubmitted ({len(stale_jobs) + len(stale_schols)})",
            stale_rows, "#ea580c"
        )

    dashboard_url = f"{API_BASE_URL}/dashboard"
    subject = f"[Job Hunter KE] {total} item{'s' if total != 1 else ''} need your attention"

    body = f"""
    <p style="font-size:15px;margin:0 0 20px">
      You have <strong>{total} item{'s' if total != 1 else ''}</strong> requiring action on your Job Hunter KE dashboard.
    </p>

    {sections}

    <div style="margin-top:24px;text-align:center">
      <a href="{dashboard_url}"
         style="display:inline-block;background:#6d28d9;color:#fff;padding:12px 32px;
                border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">
        Open Dashboard →
      </a>
    </div>

    <p style="margin-top:24px;font-size:12px;color:#aaa;text-align:center">
      You're receiving this because deadline reminders are enabled.<br>
      Manage preferences in your <a href="{dashboard_url}/settings" style="color:#6d28d9">Settings</a>.
    </p>
    """

    return send_email(to, subject, _base_html("Your Daily Application Digest", body))


def notify_task_complete(task: dict, recipient: Optional[str] = None) -> bool:
    """Notify user when a background task (scrape/generate-docs) completes."""
    to = recipient or REVIEW_EMAIL
    if not to:
        return False

    task_type = task.get("type", "task")
    result    = task.get("result_json") or {}
    status    = task.get("status", "done")
    err       = task.get("error", "")

    if status == "failed":
        subject = f"[Job Hunter] Task failed: {task_type}"
        body    = f"<p>Task <b>{task_type}</b> failed.</p><pre>{err}</pre>"
    else:
        subject  = f"[Job Hunter] {task_type.replace('_',' ').title()} complete"
        scraped  = result.get("scraped", "")
        new_docs = result.get("new", result.get("processed", ""))
        body = f"""
        <p>Background task <b>{task_type}</b> completed successfully.</p>
        {'<p>Scraped: <b>' + str(scraped) + '</b> | New: <b>' + str(new_docs) + '</b></p>' if scraped else ''}
        {'<p>Processed: <b>' + str(new_docs) + '</b> records</p>' if new_docs and not scraped else ''}
        <p><a href="{API_BASE_URL}/dashboard">Open dashboard to review →</a></p>
        """

    return send_email(to, subject, _base_html(subject, body))
