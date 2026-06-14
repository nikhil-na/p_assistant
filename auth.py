# auth_trigger.py
import os
from gmail_auth import get_google_service

if __name__ == "__main__":
    # 1. Delete old token if it exists to force a fresh scope request
    if os.path.exists("token.json"):
        os.remove("token.json")
        print("Removed old token.json.")

    print("Opening browser for Google Authentication (Gmail + Calendar)...")
    
    # 2. Trigger the login flow
    get_google_service()
    
    print("\nSuccess! A new token.json has been generated with all required permissions.")