"""
Outbound email transport.

This exists because the previous implementation could not report failure.
`_deliver_reset_email` returned early when SMTP was unconfigured and caught
every exception with `logger.exception`, while the endpoint still answered
"if that account exists, we have emailed you". A password reset that is never
delivered and never reported is indistinguishable from a reset that worked, so
the account owner was told nothing and support had nothing to look at.

Two rules hold for every transport here:

1. **Never raise.** A transport returns a `DeliveryResult` describing what
   happened. Callers persist it. A mail provider being down must not turn a
   password reset into a 500, and must not stop the in-app channel or the audit
   record from happening.

2. **Never claim success it cannot verify.** `console` reports
   `status="logged"`, not `sent`, because nothing left the process. Anything
   that reports `sent` has had the provider accept the message.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Statuses a delivery can end in. `logged` is deliberately distinct from
# `sent`: it means the message was written locally, not transmitted.
STATUS_SENT = "sent"
STATUS_LOGGED = "logged"
STATUS_SKIPPED = "skipped_unconfigured"
STATUS_FAILED = "failed"


@dataclass
class DeliveryResult:
    """What actually happened to one message."""
    status: str
    provider: str
    detail: str = ""
    error: str = ""

    @property
    def delivered(self) -> bool:
        """True only when a provider accepted the message."""
        return self.status == STATUS_SENT

    def __bool__(self) -> bool:
        return self.delivered


# --------------------------------------------------------------------------- #
# transports
# --------------------------------------------------------------------------- #

def _send_console(to: str, subject: str, body: str) -> DeliveryResult:
    """Write the message to the log and to ./dev_mail/. Development only.

    Deliberately honest about the outcome: this is how a developer reads the
    reset link without an SMTP account, and the recorded status says `logged`
    so nobody later mistakes a dev mailbox for real delivery.
    """
    text = (
        f"Date: {os.environ.get('EMAIL_DATE', '')}\n"
        f"To: {to}\nFrom: {settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>\n"
        f"Subject: {subject}\n\n{body}\n"
    )
    logger.info("DEV MAIL (transport=console) to=%s subject=%s", to, subject)
    try:
        directory = settings.DEV_MAIL_DIR
        os.makedirs(directory, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "@._-" else "_" for c in to)
        path = os.path.join(directory, f"{safe}.txt")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n" + "-" * 60 + "\n")
        return DeliveryResult(STATUS_LOGGED, "console", detail=path)
    except OSError as exc:
        # Still logged above, so treat the file as best-effort.
        return DeliveryResult(STATUS_LOGGED, "console",
                              error=f"could not write {settings.DEV_MAIL_DIR}: {exc}")


def _send_smtp(to: str, subject: str, body: str) -> DeliveryResult:
    if not (settings.SMTP_USER and settings.SMTP_PASSWORD):
        return DeliveryResult(
            STATUS_SKIPPED, "smtp",
            error="SMTP_USER/SMTP_PASSWORD are not configured",
        )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    message["To"] = to
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT,
                          timeout=settings.SMTP_TIMEOUT_SECONDS) as server:
            if settings.SMTP_USE_TLS:
                server.starttls(context=ssl.create_default_context())
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        return DeliveryResult(STATUS_SENT, "smtp")
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP delivery to %s failed: %s", to, exc)
        return DeliveryResult(STATUS_FAILED, "smtp", error=str(exc))


def _post_json(url: str, payload: dict, headers: dict) -> DeliveryResult:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=settings.EMAIL_HTTP_TIMEOUT_SECONDS
        ) as response:
            if 200 <= response.status < 300:
                return DeliveryResult(STATUS_SENT, headers.get("X-Provider", "http"))
            return DeliveryResult(STATUS_FAILED, headers.get("X-Provider", "http"),
                                  error=f"HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        return DeliveryResult(STATUS_FAILED, headers.get("X-Provider", "http"),
                              error=f"HTTP {exc.code}: {body}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return DeliveryResult(STATUS_FAILED, headers.get("X-Provider", "http"),
                              error=str(exc))


def _send_brevo(to: str, subject: str, body: str) -> DeliveryResult:
    if not settings.BREVO_API_KEY:
        return DeliveryResult(STATUS_SKIPPED, "brevo",
                              error="BREVO_API_KEY is not configured")
    sender = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    result = _post_json(
        "https://api.brevo.com/v3/smtp/email",
        {"sender": sender, "to": [{"email": to}], "subject": subject,
         "textContent": body},
        {"api-key": settings.BREVO_API_KEY, "X-Provider": "brevo",
         "accept": "application/json"},
    )
    return result


def _send_resend(to: str, subject: str, body: str) -> DeliveryResult:
    if not settings.RESEND_API_KEY:
        return DeliveryResult(STATUS_SKIPPED, "resend",
                              error="RESEND_API_KEY is not configured")
    result = _post_json(
        "https://api.resend.com/emails",
        {"from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
         "to": [to], "subject": subject, "text": body},
        {"Authorization": f"Bearer {settings.RESEND_API_KEY}",
         "X-Provider": "resend"},
    )
    return result


_TRANSPORTS = {
    "console": _send_console,
    "smtp": _send_smtp,
    "brevo": _send_brevo,
    "resend": _send_resend,
}


def send_email(to: str, subject: str, body: str) -> DeliveryResult:
    """
    Send one message through the configured transport.

    Never raises: an unreachable mail provider is reported, not propagated, so
    that the caller's remaining work -- auditing, in-app notification, telling
    the user their request was received -- still happens.
    """
    name = (settings.EMAIL_TRANSPORT or "console").strip().lower()
    transport = _TRANSPORTS.get(name)
    if transport is None:
        # An unrecognised transport is a configuration error. Say so loudly and
        # fall back to the log rather than silently dropping the message.
        logger.error(
            "EMAIL_TRANSPORT=%r is not a known transport (%s); falling back to "
            "console", name, ", ".join(sorted(_TRANSPORTS)),
        )
        result = _send_console(to, subject, body)
        result.error = f"unknown EMAIL_TRANSPORT={name!r}"
        return result
    try:
        return transport(to, subject, body)
    except Exception as exc:  # defensive: a transport must not escape
        logger.exception("Email transport %r raised", name)
        return DeliveryResult(STATUS_FAILED, name, error=str(exc))


def transport_status() -> dict:
    """
    Describe whether real delivery is possible right now.

    Used by the diagnostics endpoint so an operator can see *before* a user
    complains that no mail can leave the process.
    """
    name = (settings.EMAIL_TRANSPORT or "console").strip().lower()
    configured = {
        "console": True,
        "smtp": bool(settings.SMTP_USER and settings.SMTP_PASSWORD),
        "brevo": bool(settings.BREVO_API_KEY),
        "resend": bool(settings.RESEND_API_KEY),
    }.get(name, False)
    return {
        "transport": name,
        "configured": configured,
        "can_deliver": configured and name != "console",
        "note": (
            "console transport: messages are written to the log and "
            f"{settings.DEV_MAIL_DIR}/, not transmitted. Development only."
            if name == "console" else ""
        ),
    }
