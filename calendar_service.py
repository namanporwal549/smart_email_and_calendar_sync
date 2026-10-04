from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Popup reminders added to every event this app creates
ONE_DAY_BEFORE_MINUTES = 1440
TWO_HOURS_BEFORE_MINUTES = 120


def get_calendar_service(credentials):
    """Create Google Calendar API service."""

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


def create_calendar_event(
    credentials,
    summary,
    description,
    start_time,
    end_time,
    event_id=None
):
    """Create an event in the user's primary Google Calendar."""

    service = get_calendar_service(credentials)

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_time,
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time,
            "timeZone": "Asia/Kolkata",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {
                    "method": "popup",
                    "minutes": ONE_DAY_BEFORE_MINUTES
                },
                {
                    "method": "popup",
                    "minutes": TWO_HOURS_BEFORE_MINUTES
                },
            ],
        },
    }

    if event_id:
        event["id"] = event_id

    try:
        created_event = service.events().insert(
            calendarId="primary",
            body=event
        ).execute()

        return created_event

    except HttpError as e:

        if e.resp.status == 409:
            return {
                "already_exists": True,
                "summary": summary
            }

        raise


def get_calendar_events(
    credentials,
    time_min=None,
    time_max=None,
    max_results=100
):
    """Get events from the user's primary Google Calendar."""

    service = get_calendar_service(credentials)

    try:

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        return events_result.get(
            "items",
            []
        )

    except HttpError:
        raise