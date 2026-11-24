"""Delivery: Slack incoming webhook and SMTP e-mail.

Brand YAML names the env vars to read, e.g.::

    notify:
      slack_webhook_env: SLACK_WEBHOOK_URL_BOYER
      email_to_env: BRIEFING_EMAIL_TO_BOYER
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import Brand, env
from .http import session

log = logging.getLogger(__name__)
SLACK_LIMIT = 2900  # Slack section blocks cap at 3000 chars


def to_slack_mrkdwn(md: str) -> str:
    out = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("#"):
            out.append(f"*{s.lstrip('#').strip()}*")
        else:
            out.append(line.replace("**", "*"))
    return "\n".join(out)


def send_slack(brand: Brand, title: str, markdown: str, report_url: str | None = None) -> bool:
    url = env(brand.raw.get("notify", {}).get("slack_webhook_env"))
    if not url:
        log.info("[%s] Slack webhook not configured; skipping.", brand.slug)
        return False
    text = to_slack_mrkdwn(markdown)
    chunks = [text[i:i + SLACK_LIMIT] for i in range(0, len(text), SLACK_LIMIT)][:12]
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": title[:150]}}]
    blocks += [{"type": "section", "text": {"type": "mrkdwn", "text": c}} for c in chunks]
    if report_url:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"<{report_url}|Full report>"}]})
    r = session().post(url, json={"text": title, "blocks": blocks}, timeout=30)
    ok = r.status_code < 300
    if not ok:
        log.error("[%s] Slack returned %s", brand.slug, r.status_code)
    return ok


def send_email(brand: Brand, subject: str, markdown: str) -> bool:
    cfg = brand.raw.get("notify", {})
    to = env(cfg.get("email_to_env"))
    host, user, pwd = env("SMTP_HOST"), env("SMTP_USER"), env("SMTP_PASSWORD")
    if not (to and host and user and pwd):
        log.info("[%s] E-mail not configured; skipping.", brand.slug)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = env("SMTP_FROM", user)
    msg["To"] = to
    msg.set_content(markdown)
    try:
        import markdown as mdlib  # optional nicer HTML body

        msg.add_alternative(mdlib.markdown(markdown, extensions=["tables"]), subtype="html")
    except ImportError:
        pass
    port = int(env("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(user, pwd)
        smtp.send_message(msg)
    return True
