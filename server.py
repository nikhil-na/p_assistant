from turtle import st
from fastmcp import FastMCP
import json
import sys
import base64
from typing import Optional
from utils import clean_email


from langchain_core import outputs
from gmail_auth import get_gmail_service

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
    service = get_gmail_service()
    query = f"from: {name}" if name else ""
    print(query)
    results = service.users().messages().list(userId="me", q=query, maxResults=1).execute()

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
def send_email():

    """
    Send an email to the user.
    """
    return "Sent email to the user"

@mcp.tool
def draft_email():

    """
    Draft an email to the user.
    """
    return "Drafted email to the user"

@mcp.tool
def search_contats():

    """
    Search for contacts in the user's address book.
    """
    return "Searched for contacts in the user's address book"

@mcp.tool
def save_contact():

    """
    Save a contact to the user's address book.
    """
    return "Saved contact to the user's address book"


# FOR CALENDAR SECTION
@mcp.tool
def get_calendar_events():

    """
    Get all calendar events from the user's calendar.
    """
    return "Got all calendar events from the user's calendar"

@mcp.tool
def create_calendar_event():

    """
    Create a new calendar event in the user's calendar.
    """
    return "Created a new calendar event in the user's calendar"

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
    mcp.run(transport="stdio")