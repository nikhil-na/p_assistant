from turtle import st
from fastmcp import FastMCP
import json
import sys
import base64
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from utils import clean_email
from datetime import datetime


from langchain_core import outputs
from gmail_auth import get_google_service

mcp = FastMCP("p_a_server")

with open("dummy.json", "r") as f:
    data = json.load(f)

MOCK_EMAILS = data["mock_emails"]
MOCK_GMAIL_CONTACTS = data["mock_gmail_contacts"]


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
def get_calendar_events():

    """
    Get all calendar events from the user's calendar.
    """
    return "Got all calendar events from the user's calendar"

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
def update_calendar_event():

    """
    Update a calendar event in the user's calendar.
    """
    return "Updated a calendar event in the user's calendar"

@mcp.tool
def delete_calendar_event():

    """
    Delete a calendar event from the user's calendar.
    """
    return "Deleted a calendar event from the user's calendar"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)