import os
import secrets

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    request,
    jsonify
)

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from gmail_service import (
    get_latest_emails,
    create_email_draft,
    send_email_reply
)

from calendar_service import create_calendar_event


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    secrets.token_hex(32)
)


# =========================================================
# GOOGLE OAUTH SETTINGS
# =========================================================

CLIENT_SECRETS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events"
]

REDIRECT_URI = (
    "http://127.0.0.1:5000/oauth2callback"
)


# =========================================================
# SAVE GOOGLE CREDENTIALS
# =========================================================

def save_credentials(credentials):
    """Save Google credentials in session."""

    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


# =========================================================
# GET GOOGLE CREDENTIALS
# =========================================================

def get_credentials():

    if "credentials" not in session:
        return None

    credentials = Credentials(
        **session["credentials"]
    )

    if credentials.expired and credentials.refresh_token:

        credentials.refresh(
            Request()
        )

        save_credentials(
            credentials
        )

    return credentials


# =========================================================
# HOME / DASHBOARD
# =========================================================

@app.route("/")
def home():

    emails = []
    gmail_error = None

    if "credentials" in session:

        try:

            credentials = get_credentials()

            emails = get_latest_emails(
                credentials,
                max_results=20
            ) or []

            # Automatically add detected meetings
            for email in emails:

                if (
                    email.get("meeting_detected")
                    and email.get("meeting_start")
                    and email.get("meeting_end")
                ):

                    try:

                        event_id = (
                            "gmail"
                            + email["id"].lower()
                        )

                        event = create_calendar_event(

                            credentials=credentials,

                            summary=email["subject"],

                            description=email["body"],

                            start_time=email["meeting_start"],

                            end_time=email["meeting_end"],

                            event_id=event_id

                        )

                        if event.get("already_exists"):

                            email["calendar_status"] = (
                                "Already Added"
                            )

                        else:

                            email["calendar_status"] = (
                                "Added"
                            )

                    except Exception as calendar_error:

                        print(
                            "Calendar error:",
                            repr(calendar_error)
                        )

                        email["calendar_status"] = (
                            "Calendar Error"
                        )

        except Exception as e:

            print(
                "Gmail fetch error:",
                repr(e)
            )

            gmail_error = str(e)

            emails = []

    return render_template(

        "index.html",

        emails=emails,

        gmail_connected=(
            "credentials" in session
        ),

        gmail_error=gmail_error

    )


# =========================================================
# AI ASSISTANT CHAT
# =========================================================

@app.route(
    "/assistant/chat",
    methods=["POST"]
)
def assistant_chat():

    try:

        # -------------------------------------------------
        # Get message from frontend
        # -------------------------------------------------

        data = request.get_json(
            silent=True
        ) or {}

        message = (
            data.get("message")
            or data.get("prompt")
            or ""
        ).strip()

        if not message:

            return jsonify({

                "success": False,

                "reply": "Bhai, message empty hai."

            }), 400

        print(
            "CHAT MESSAGE:",
            message
        )


        # -------------------------------------------------
        # Import Gemini
        # -------------------------------------------------

        try:

            from google import genai

        except ImportError:

            print(
                "google-genai package not installed."
            )

            return jsonify({

                "success": False,

                "reply": (
                    "Gemini package install nahi hai. "
                    "Terminal mein pip install google-genai chalao."
                )

            }), 500


        # -------------------------------------------------
        # Gemini API Key
        # -------------------------------------------------

        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )

        if not api_key:

            print(
                "GEMINI_API_KEY not found"
            )

            return jsonify({

                "success": False,

                "reply": (
                    "Gemini API key nahi mili. "
                    "GEMINI_API_KEY check karo."
                )

            }), 500


        # -------------------------------------------------
        # Create Gemini Client
        # -------------------------------------------------

        client = genai.Client(
            api_key=api_key
        )


        # -------------------------------------------------
        # Create Gemini Prompt
        # -------------------------------------------------

        prompt = f"""
You are the AI assistant inside an Email Calendar Sync application.

You help the user with:

- Gmail emails
- upcoming meetings
- calendar events
- reminders
- email summaries
- normal questions

Be friendly, helpful and concise.

If the user asks a normal question,
answer normally.

User message:

{message}
"""


        # -------------------------------------------------
        # Generate Gemini Response
        # -------------------------------------------------

        response = client.models.generate_content(

            model="gemini-3.8-flash",

            contents=prompt

        )


        # -------------------------------------------------
        # Get Response Text
        # -------------------------------------------------

        reply = (
            getattr(
                response,
                "text",
                None
            )
            or
            "Bhai, Gemini ne koi response nahi diya."
        )


        print(
            "CHAT RESPONSE:",
            reply
        )


        return jsonify({

            "success": True,

            "reply": reply

        })


    except Exception as e:

        print(
            "ASSISTANT ERROR:",
            repr(e)
        )

        return jsonify({

            "success": False,

            "reply": (
                "Assistant mein error aa gaya. "
                "Server terminal check karo."
            ),

            "error": str(e)

        }), 500


# =========================================================
# CONNECT GMAIL
# =========================================================

@app.route("/connect-gmail")
def connect_gmail():

    flow = Flow.from_client_secrets_file(

        CLIENT_SECRETS_FILE,

        scopes=SCOPES,

        redirect_uri=REDIRECT_URI

    )

    authorization_url, state = (
        flow.authorization_url(

            access_type="offline",

            prompt="consent"

        )
    )

    session["state"] = state

    session["code_verifier"] = (
        flow.code_verifier
    )

    return redirect(
        authorization_url
    )


# =========================================================
# GOOGLE OAUTH CALLBACK
# =========================================================

@app.route("/oauth2callback")
def oauth2callback():

    state = session.get(
        "state"
    )

    if not state:

        return """
        <h2>OAuth Session Expired ❌</h2>

        <p>
            Please click Connect Gmail again.
        </p>

        <a href="/">
            Back to Dashboard
        </a>
        """


    flow = Flow.from_client_secrets_file(

        CLIENT_SECRETS_FILE,

        scopes=SCOPES,

        state=state,

        redirect_uri=REDIRECT_URI

    )


    flow.code_verifier = (
        session.get("code_verifier")
    )


    try:

        flow.fetch_token(

            authorization_response=request.url

        )


    except Exception as e:

        print(
            "OAuth error:",
            repr(e)
        )


        return f"""
        <h2>Gmail Login Error ❌</h2>

        <pre>{e}</pre>

        <br>

        <a href="/">
            Back to Dashboard
        </a>
        """


    credentials = flow.credentials


    save_credentials(
        credentials
    )


    session.pop(
        "state",
        None
    )

    session.pop(
        "code_verifier",
        None
    )


    return redirect(
        url_for("home")
    )


# =========================================================
# SAVE EMAIL DRAFT
# =========================================================

@app.route(
    "/save-draft",
    methods=["POST"]
)
def save_draft():

    if "credentials" not in session:

        return redirect(
            url_for("home")
        )


    message_id = request.form.get(
        "message_id"
    )

    reply_text = request.form.get(
        "reply_text",
        ""
    )


    if not message_id:

        return """
        <h2>Message ID Missing ❌</h2>

        <a href="/">
            Back to Dashboard
        </a>
        """


    try:

        credentials = get_credentials()


        create_email_draft(

            credentials=credentials,

            message_id=message_id,

            reply_text=reply_text

        )


        return redirect(
            url_for("home")
        )


    except Exception as e:

        print(
            "Save draft error:",
            repr(e)
        )


        return f"""
        <h2>Draft Save Failed ❌</h2>

        <pre>{e}</pre>

        <br>

        <a href="/">
            Back to Dashboard
        </a>
        """


# =========================================================
# SEND EMAIL REPLY
# =========================================================

@app.route(
    "/send-reply",
    methods=["POST"]
)
def send_reply():

    if "credentials" not in session:

        return redirect(
            url_for("home")
        )


    message_id = request.form.get(
        "message_id"
    )

    reply_text = request.form.get(
        "reply_text",
        ""
    )


    if not message_id:

        return """
        <h2>Message ID Missing ❌</h2>

        <a href="/">
            Back to Dashboard
        </a>
        """


    if not reply_text.strip():

        return """
        <h2>Reply Cannot Be Empty ❌</h2>

        <a href="/">
            Back to Dashboard
        </a>
        """


    try:

        credentials = get_credentials()


        send_email_reply(

            credentials=credentials,

            message_id=message_id,

            reply_text=reply_text

        )


        return redirect(
            url_for("home")
        )


    except Exception as e:

        print(
            "Send reply error:",
            repr(e)
        )


        return f"""
        <h2>Reply Send Failed ❌</h2>

        <pre>{e}</pre>

        <br>

        <a href="/">
            Back to Dashboard
        </a>
        """


# =========================================================
# TEST CALENDAR
# =========================================================

@app.route("/test-calendar")
def test_calendar():

    if "credentials" not in session:

        return """
        <h2>Gmail Not Connected ❌</h2>

        <a href="/">
            Back to Dashboard
        </a>
        """


    try:

        credentials = get_credentials()


        event = create_calendar_event(

            credentials=credentials,

            summary="Team Meeting - Test",

            description=(
                "This is a test event created by "
                "the Email Calendar Sync app."
            ),

            start_time="2026-10-05T15:00:00",

            end_time="2026-10-05T16:00:00"

        )


        return f"""
        <h2>
            Calendar Event Created Successfully! ✅
        </h2>

        <p>
            Event: {event.get("summary")}
        </p>

        <p>
            Start: October 5, 2026 at 3:00 PM
        </p>

        <p>
            <a
                href="{event.get("htmlLink")}"
                target="_blank"
            >
                Open Google Calendar Event
            </a>
        </p>

        <p>
            <a href="/">
                Back to Dashboard
            </a>
        </p>
        """


    except Exception as e:

        print(
            "Calendar error:",
            repr(e)
        )


        return f"""
        <h2>
            Calendar Event Creation Failed ❌
        </h2>

        <pre>{e}</pre>

        <p>
            <a href="/">
                Back to Dashboard
            </a>
        </p>
        """


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop(
        "credentials",
        None
    )

    session.pop(
        "state",
        None
    )

    session.pop(
        "code_verifier",
        None
    )


    return redirect(
        url_for("home")
    )


# =========================================================
# START FLASK SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )