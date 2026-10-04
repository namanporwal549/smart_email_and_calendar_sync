import base64
import html
import re

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build


def _get_header(headers, name):
    """Find one header in email headers."""

    for header in headers:

        if header["name"].lower() == name.lower():

            return header["value"]

    return ""


def _format_date(date_text):
    """Convert email date into readable format."""

    try:

        return parsedate_to_datetime(
            date_text
        ).strftime("%Y-%m-%d %H:%M")

    except Exception:

        return date_text


def _decode(data):
    """Decode Gmail base64 email body."""

    data += "=" * (-len(data) % 4)

    return base64.urlsafe_b64decode(
        data
    ).decode(
        "utf-8",
        errors="replace"
    )


def _extract_body(payload):
    """Extract plain text body from Gmail payload."""

    if (
        payload.get("mimeType") == "text/plain"
        and payload.get("body", {}).get("data")
    ):

        return _decode(
            payload["body"]["data"]
        )


    for part in payload.get("parts", []):

        text = _extract_body(part)

        if text:

            return text


    return ""


def _classify_email(subject, body):
    """Classify email as Important or Normal."""

    text = f"{subject} {body}".lower()


    important_keywords = [

        "urgent",
        "important",
        "asap",
        "action required",
        "action needed",
        "deadline",
        "due date",
        "meeting",
        "appointment",
        "interview",
        "interview invitation",
        "schedule",
        "scheduled",
        "payment",
        "invoice",
        "bill",
        "account",
        "security alert",
        "security",
        "verification",
        "verify your account",
        "password",
        "reset password",
        "login",
        "sign-in",
        "signin",
        "confirmation",
        "confirm",
        "application",
        "offer",
        "job",
        "hiring",
        "project",
        "client",
        "submission",
        "document",
        "approval",
        "approved",
        "rejected",
        "reminder",

    ]


    return any(
        keyword in text
        for keyword in important_keywords
    )


def _detect_meeting(subject, body):
    """Detect meeting email."""

    text = f"{subject} {body}".lower()


    meeting_keywords = [

        "meeting",
        "appointment",
        "interview",
        "calendar invite",
        "calendar invitation",
        "zoom meeting",
        "google meet",
        "teams meeting",
        "meet link",
        "scheduled for",
        "conference call",

    ]


    has_meeting_keyword = any(
        keyword in text
        for keyword in meeting_keywords
    )


    date_patterns = [

        r"\b\d{4}-\d{1,2}-\d{1,2}\b",

        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",

        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b",

        r"\b(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\s+\d{1,2}"
        r"(?:,\s*\d{4})?\b",

    ]


    has_date = any(
        re.search(pattern, text)
        for pattern in date_patterns
    )


    time_pattern = (
        r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b"
        r"|\b(?:[01]?\d|2[0-3]):[0-5]\d\b"
    )


    has_time = bool(
        re.search(
            time_pattern,
            text
        )
    )


    return (
        has_meeting_keyword
        and has_date
        and has_time
    )


def _extract_meeting_datetime(subject, body):
    """Extract meeting start and end datetime."""

    text = f"{subject} {body}"


    pattern = (
        r"\b("
        r"January|February|March|April|May|June|July|August|"
        r"September|October|November|December"
        r")\s+"
        r"(\d{1,2}),?\s+"
        r"(\d{4})"
        r"\s+(?:at|@)\s+"
        r"(\d{1,2})"
        r"(?::(\d{2}))?"
        r"\s*(AM|PM)"
    )


    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )


    if not match:

        return None, None


    month = match.group(1)
    day = match.group(2)
    year = match.group(3)
    hour = match.group(4)
    minute = match.group(5) or "00"
    am_pm = match.group(6).upper()


    date_time_text = (
        f"{month} {day} {year} "
        f"{hour}:{minute} {am_pm}"
    )


    try:

        start = datetime.strptime(
            date_time_text,
            "%B %d %Y %I:%M %p"
        )


        end = start + timedelta(
            hours=1
        )


        return (
            start.strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            end.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        )


    except ValueError:

        return None, None


def _generate_draft_reply(
    subject,
    body,
    meeting_detected
):
    """Generate automatic suggested reply."""

    text = f"{subject} {body}".lower()


    if meeting_detected:

        return (
            "Hi,\n\n"
            "Thank you for sharing the meeting details. "
            "I have noted the meeting and added it to my calendar.\n\n"
            "Looking forward to the discussion.\n\n"
            "Best regards"
        )


    if "interview" in text:

        return (
            "Hi,\n\n"
            "Thank you for the interview invitation. "
            "I appreciate the opportunity and look forward "
            "to discussing this further.\n\n"
            "Best regards"
        )


    if any(
        keyword in text
        for keyword in [
            "confirmation",
            "confirm",
            "appointment"
        ]
    ):

        return (
            "Hi,\n\n"
            "Thank you for the confirmation. "
            "I have received the details and noted them.\n\n"
            "Best regards"
        )


    if any(
        keyword in text
        for keyword in [
            "payment",
            "invoice",
            "bill"
        ]
    ):

        return (
            "Hi,\n\n"
            "Thank you for sharing the payment details. "
            "I have received the information and will review it.\n\n"
            "Best regards"
        )


    return (
        "Hi,\n\n"
        "Thank you for your email. "
        "I have received your message and will review it shortly.\n\n"
        "Best regards"
    )


def get_latest_emails(credentials, max_results=20):
    """Read latest Gmail inbox emails."""

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )


    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=max_results
    ).execute()


    messages = result.get(
        "messages",
        []
    )


    emails = []


    for message in messages:

        full = service.users().messages().get(
            userId="me",
            id=message["id"],
            format="full"
        ).execute()


        headers = full["payload"].get(
            "headers",
            []
        )


        snippet = html.unescape(
            full.get(
                "snippet",
                ""
            )
        )


        body = (
            _extract_body(
                full["payload"]
            )
            or snippet
        )


        subject = _get_header(
            headers,
            "Subject"
        ) or "(No Subject)"


        sender = _get_header(
            headers,
            "From"
        ) or "(Unknown sender)"


        date_text = _get_header(
            headers,
            "Date"
        )


        important = _classify_email(
            subject,
            body
        )


        meeting_detected = _detect_meeting(
            subject,
            body
        )


        start_time = None
        end_time = None


        if meeting_detected:

            start_time, end_time = (
                _extract_meeting_datetime(
                    subject,
                    body
                )
            )


        draft_reply = _generate_draft_reply(
            subject,
            body,
            meeting_detected
        )


        emails.append({

            "id": message["id"],

            "subject": subject,

            "sender": sender,

            "date": _format_date(
                date_text
            ),

            "snippet": snippet,

            "body": body,

            "important": important,

            "meeting_detected": meeting_detected,

            "meeting_start": start_time,

            "meeting_end": end_time,

            "calendar_status": (
                "Meeting Detected"
                if meeting_detected
                else "Not Added"
            ),

            "draft_status": "Draft Ready",

            "draft_reply": draft_reply,

        })


    return emails


def _get_original_message(
    service,
    message_id
):
    """Get original Gmail message details."""

    original = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=[
            "Subject",
            "From",
            "Message-ID"
        ]
    ).execute()


    headers = original["payload"].get(
        "headers",
        []
    )


    original_subject = _get_header(
        headers,
        "Subject"
    )


    original_from = _get_header(
        headers,
        "From"
    )


    message_header_id = _get_header(
        headers,
        "Message-ID"
    )


    if not message_header_id:

        message_header_id = message_id


    reply_subject = original_subject


    if not reply_subject.lower().startswith("re:"):

        reply_subject = "Re: " + reply_subject


    return (
        original,
        original_from,
        reply_subject,
        message_header_id
    )


def _create_raw_reply(
    original_from,
    reply_subject,
    message_header_id,
    reply_text
):
    """Create encoded Gmail reply message."""

    raw_message = (
        f"To: {original_from}\r\n"
        f"Subject: {reply_subject}\r\n"
        f"In-Reply-To: {message_header_id}\r\n"
        f"References: {message_header_id}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{reply_text}"
    )


    return (
        base64.urlsafe_b64encode(
            raw_message.encode("utf-8")
        ).decode("utf-8")
    )


def create_email_draft(
    credentials,
    message_id,
    reply_text
):
    """Save reply as Gmail Draft."""

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )


    (
        original,
        original_from,
        reply_subject,
        message_header_id
    ) = _get_original_message(
        service,
        message_id
    )


    encoded_message = _create_raw_reply(
        original_from=original_from,
        reply_subject=reply_subject,
        message_header_id=message_header_id,
        reply_text=reply_text
    )


    draft_body = {

        "message": {

            "raw": encoded_message,

            "threadId": original.get(
                "threadId"
            )

        }

    }


    draft = service.users().drafts().create(
        userId="me",
        body=draft_body
    ).execute()


    return draft


def send_email_reply(
    credentials,
    message_id,
    reply_text
):
    """Send reply immediately through Gmail."""

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )


    (
        original,
        original_from,
        reply_subject,
        message_header_id
    ) = _get_original_message(
        service,
        message_id
    )


    encoded_message = _create_raw_reply(
        original_from=original_from,
        reply_subject=reply_subject,
        message_header_id=message_header_id,
        reply_text=reply_text
    )


    message_body = {

        "raw": encoded_message,

        "threadId": original.get(
            "threadId"
        )

    }


    sent_message = service.users().messages().send(
        userId="me",
        body=message_body
    ).execute()


    return sent_message