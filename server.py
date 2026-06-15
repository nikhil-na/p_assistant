from turtle import st
from fastmcp import FastMCP
import json
import sys
import base64
import pytz
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from utils import clean_email
from datetime import datetime
from langchain_core.tools import tool

from langchain_core import outputs
from gmail_auth import get_google_service

mcp = FastMCP("p_a_server")

with open("dummy.json", "r") as f:
    data = json.load(f)

MOCK_EMAILS = data["mock_emails"]
MOCK_GMAIL_CONTACTS = data["mock_gmail_contacts"]

## TOOLS
@tool
def get_current_datetime(timezone:str='America/Chicago'):
    """
    Get the current date and time. Always call this tool first when the user
    mentions relative dates like 'tomorrow', 'next week', 'in 2 hours', 'on Friday'.
    Args:
        timezone: the timezone to use, e.g. 'America/New_York', 'Asia/Kathmandu', 'UTC'
        timezone: defaults to 'America/Chicago' if not specified by user

    Returns:
        Current date and time as a string
    """
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    return (
        f"Current datetime: {now.strftime('%A, %B %d, %Y %I:%M %p %Z')}\n"
        f"ISO 8601: {now.isoformat()}\n"
        f"Timezone offset: {now.strftime('%z')}\n"
        f"Use this offset when constructing datetimes: e.g. 2026-06-15T00:00:00{now.strftime('%z')}"
    )

#HELPER FUNCTION
def get_all_events(timeMin:datetime, timeMax:datetime):
    """
    Get calendar events within a specified time range.

    Args:
        timeMin datetime: Start time for retrieving events.
        timeMax datetime: End time for retrieving events.

    Returns:
        str: All calendar events from the user's calendar within the specified time range.
    """

    service = get_google_service("calendar")

    events_result = service.events().list(calendarId="primary", timeMin=timeMin.isoformat(), timeMax=timeMax.isoformat(), singleEvents=True).execute()
    
    return events_result.get('items', [])

# FOR EMAILS SECTION
@mcp.tool
def get_emails(name: Optional[str] = None):

    """
    Get emails from Gmail inbox.
    If name is provided, filters emails from that sender.
    Args:
        name: sender name or email to filter by
        max_results: how many emails to fetch
    Returns:
        A readable string of emails
    """
    service = get_google_service(action="email")
    query = f"from: {name}" if name else ""
    results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()

    # print(f"DEBUG {results}", file=sys.stderr) 
    #       => DEBUG {'messages': [{'id': '19e8f561075cb872', 'threadId': '19e8f561075cb872'}], 'nextPageToken': '00107668162830157987', 'resultSizeEstimate': 201}
    
    messages = results.get("messages", [])

    if not messages:
        print("No messages found.")
        return

    ## FOR DEBUG
    # detail = service.users().messages().get(userId="me", id=messages[0]["id"], format="full").execute()
    # print(json.dumps(detail, indent=2), file=sys.stderr)

    
    output = []
    for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"]).execute()

        """
            eg, msg looks like: {
                "id": "18f3a2b1c4d5e6f7",
                "threadId": "18f3a2b1c4d5e6f7",
                "snippet": "Hey, just following up on...",
                "payload": {
                    "headers": [
                        { "name": "From",    "value": "Bob Smith <bob@gmail.com>" },
                        { "name": "To",      "value": "you@gmail.com" },
                        { "name": "Subject", "value": "Follow up" },
                        { "name": "Date",    "value": "Thu, 11 Jun 2026 10:30:00 +0000" }
                    ],
                    "mimeType": "text/plain",
                    "body": {
                    "data": "SGVsbG8gd29ybGQ=",
                    "size": 11
                    }
                }
            }
        """
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        
        subject = headers.get("Subject", "(no-subject)")
        from_ = headers.get("From", "(unknown)")
        to = headers.get("To", "(unknown)")
        date = headers.get("Date", "")

        payload = msg["payload"]
        
        if "body" in payload:
            data = payload["body"].get("data", "")
            decoded_bytes = base64.urlsafe_b64decode(data)
            body = decoded_bytes.decode('utf-8')

        output.append(f"From: {from_}\n To: {to}\n Subject: {subject}\n Date: {date}\n Body: {body[:500]}\n")
        # print(f"DEBUG {output}", file=sys.stderr)

    return clean_email(output)

@mcp.tool
async def draft_send_email(to: str, subject: str, query: str):

    """
    Drafts an email to the specified address for human review.

    Args:
        to (str): Recipient's email address.
        subject (str): Subject line of the email.
        query (str): Instructions or message content provided by the user.

    Returns:
        dict: Contains the draft email details for review, including recipient, subject, and generated body.
    """
    return json.dumps({
        "action": "review_email",
        "to": to,
        "subject": subject,
        "body": query
    })

# FOR CALENDAR SECTION
@mcp.tool
def get_calendar_events(timeMin:Optional[datetime], timeMax:Optional[datetime]):

    """
    Get calendar events within a specified time range.

    Args:
        timeMin Optional(datetime): Start time for retrieving events.
        timeMax Optional(datetime): End time for retrieving events.

    Returns:
        str: All calendar events from the user's calendar within the specified time range.
    """

    events = get_all_events(timeMin, timeMax)
    return f"Got all calendar events from the user's calendar: {events}"

@mcp.tool
def create_calendar_event(
        summary: str,
        attendees: list, 
        start_date_time: datetime,
        location: str,
        end_date_time: datetime,
        timezone:str,  
        notes: str
    ):
    """
    Create a new calendar event in the user's calendar. Use this tool when you want to schedule a new event on the user's calendar.

    Args:
        summary (str): What event is about.
        attendees (list): List of attendees for the event.
        start_date_time (datetime): Start date and time for the event.
        location (str): Location of the event.
        end_date_time (datetime): End date and time for the event.
        timezone (str): Timezone for the event.
        notes (str): Additional notes or description for the event.

    Returns:
        str: Confirmation message that the event was created.
    """

    service = get_google_service("calendar")

    formatted_attendees=[{"email": email for email in attendees}]

    event_details = {
        "summary": summary,
        "location": location,
        "description": notes,
        "attendees": formatted_attendees,
        "start": {
            "dateTime": start_date_time.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_date_time.isoformat(),
            "timeZone": timezone,
        }
    }

    event = service.events().insert(calendarId='primary', body=event_details).execute()

    return f"Created a new calendar event in the user's calendar: {event.get('htmlLink')}"

@mcp.tool
def update_calendar_event(initial_time_min: datetime, initial_time_max: datetime, new_time_min: datetime, new_time_max: datetime, email: Optional[str], summary: Optional[str], name: Optional[str]):

    """
    Update a calendar event in the user's calendar. Use this method when the user wants to make a change to their event. This should have a human approval too where the user should be prompted to give his feedback.
    
    Args:
        initial_time_min (datetime): Start time for retrieving the event.
        initial_time_max (datetime): End time for retrieving the event.
        new_time_min (datetime): New start time for the event.
        new_time_max (datetime): New end time for the event.
        email (Optional[str]): Email address of the attendee if provided to modify.
        summary (Optional[str]): Name of the event to update.
        name (Optional[str]): Name of the attendee if provided
    
    Returns:
        str: Confirmation message that the event was updated.
    """

    ## TODO: Shift time and Duration: (e.g., "Move my 30-minute sync from 2 PM to 4 PM").
    ## TODO: Modify Attendees.
        # Add: Append a new email dictionary {"email": "new_guest@example.com"} to the existing list.

        # Remove: Filter out a specific email from the existing list before sending the update.

    service = get_google_service("calendar")
    events = get_all_events(initial_time_min, initial_time_max)

    updated_body = {
        "start": {"dateTime": new_time_min.isoformat(), "timeZone": "America/Chicago"},
        "end": {"dateTime": new_time_max.isoformat(), "timeZone": "America/Chicago"},
    }

    if not events:
        return "No calendar event found!"

    match_found = None
    for event in events:
        attendees = event.get("attendees", [])
        for attendee in attendees:
            if email and attendee.get("email", "").lower() == email.strip().lower():
                match_found = True
            if name and attendee.get("displayName", "") == name.strip().lower():
                match_found = True
        if initial_time_min.isoformat() <= event.get("start", {}).get("dateTime", "")<= initial_time_max.isoformat():
            match_found=True
        
        if match_found:
            event_id = event["id"]
            service.events().patch(calendarId="primary", eventId=event_id, sendUpdates="all", body=updated_body).execute()

    return "Updated a calendar event in the user's calendar"

@mcp.tool
def delete_calendar_event(email:str, timeMin:Optional[datetime], timeMax:Optional[datetime]):

    """
    Delete calendar events from the user's calendar.

    Args:
        email: The email address of the attendee to match.
        timeMin Optional(datetime): Start time for retrieving events.
        timeMax Optional(datetime): End time for retrieving events.

    Returns:
        str: Confirmation message that the event was deleted.
    """

    service = get_google_service("calendar")
    events = get_all_events(timeMin, timeMax)

    if not events:
        return f"Didn't find the event with the {email}"

    for event in events:
        attendees = event.get("attendees", [])
        for attendee in attendees:
            debug_email = attendee.get("email")
            print(f"DEBUG EMAIL FINAL: {debug_email}", file=sys.stderr)
            if attendee.get("email", "").lower() == email.lower().strip():
                event_id = event["id"]
                service.events().delete(calendarId="primary", eventId=event_id).execute()
            else:
                return f"The email didn't match."
    return "The event is successfully deleted!"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)