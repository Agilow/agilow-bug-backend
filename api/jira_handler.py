"""
Simplified Jira Handler for Bug Reports
Handles Jira API operations for creating bug report tickets.
"""

import requests
import json
import os
import base64
from typing import Optional, Dict, Any, List

# Global Jira credentials
JIRA_API_KEY = None
JIRA_BASE_URL = None
JIRA_PROJECT_KEY = None
JIRA_EMAIL = None


def _get_jira_auth_headers() -> Optional[Dict[str, str]]:
    """Get properly formatted Jira authentication headers."""
    if JIRA_EMAIL and JIRA_API_KEY:
        auth_string = f"{JIRA_EMAIL}:{JIRA_API_KEY}"
    else:
        auth_string = JIRA_API_KEY
        if not auth_string or ':' not in auth_string:
            print("⚠️ Warning: Need email address for Jira Cloud authentication")
            return None
    
    auth_b64 = base64.b64encode(auth_string.encode('ascii')).decode('ascii')
    
    return {
        'Accept': 'application/json',
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/json'
    }


def set_jira_credentials(api_key=None, base_url=None, project_key=None, email=None) -> bool:
    """Set Jira credentials from parameters or environment variables."""
    global JIRA_API_KEY, JIRA_BASE_URL, JIRA_PROJECT_KEY, JIRA_EMAIL
    
    # Set API key
    if api_key and api_key != "undefined" and api_key.strip():
        JIRA_API_KEY = api_key
    else:
        JIRA_API_KEY = os.getenv("JIRA_API_KEY")
    
    # Set base URL
    if base_url and base_url != "undefined" and base_url.strip():
        JIRA_BASE_URL = base_url
    else:
        JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
    
    # Set project key
    if project_key and project_key != "undefined" and project_key.strip():
        JIRA_PROJECT_KEY = project_key
    else:
        JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")
    
    # Set email
    if email and email != "undefined" and email.strip():
        JIRA_EMAIL = email
    else:
        JIRA_EMAIL = os.getenv("JIRA_EMAIL")
    
    # Validate required credentials
    if not JIRA_API_KEY or not JIRA_BASE_URL:
        print("❌ Missing required Jira credentials (API key and base URL)")
        return False
    
    print(f"🔑 Jira credentials set - Base URL: {JIRA_BASE_URL}, Project: {JIRA_PROJECT_KEY or 'Not set'}")
    return True


def fetch_users() -> List[Dict[str, Any]]:
    """Fetch all users from Jira."""
    if not JIRA_API_KEY or not JIRA_BASE_URL:
        print("❌ Cannot fetch users: Missing Jira credentials")
        return []
    
    url = f"{JIRA_BASE_URL}/rest/api/3/users/search"
    headers = _get_jira_auth_headers()
    if not headers:
        return []
    
    params = {'maxResults': 1000}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            users = response.json()
            print(f"✅ Fetched {len(users)} Jira users")
            return users
        else:
            print(f"❌ Failed to fetch users: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        return []


def find_user_by_name(user_name: str, users: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Find user by display name."""
    if users is None:
        users = fetch_users()
    
    if not users:
        return None
    
    # Exact match first
    for user in users:
        if user.get('displayName', '').lower() == user_name.lower():
            return user
    
    # Partial match
    for user in users:
        display_name = user.get('displayName', '')
        if user_name.lower() in display_name.lower():
            return user
    
    return None


def create_issue(issue_data: Dict[str, Any], project_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new issue in Jira."""
    target_project_key = project_key or JIRA_PROJECT_KEY
    
    if not JIRA_API_KEY or not JIRA_BASE_URL or not target_project_key:
        print("❌ Cannot create issue: Missing Jira credentials or project key")
        return None
    
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    headers = _get_jira_auth_headers()
    if not headers:
        return None
    
    # Extract issue data
    summary = issue_data.get('task', issue_data.get('title', ''))
    description = issue_data.get('description', '')
    assignee = issue_data.get('member', issue_data.get('assignee', ''))
    issue_type = issue_data.get('issue_type', 'Bug')
    priority = issue_data.get('priority', 'Medium')
    labels = issue_data.get('labels', [])
    
    # Build payload
    payload = {
        "fields": {
            "project": {
                "key": target_project_key
            },
            "summary": summary,
            "issuetype": {
                "name": issue_type
            }
        }
    }
    
    # Add description (Jira accepts plain text or ADF format)
    # Using plain text for simplicity - Jira will convert it
    if description:
        # For Jira Cloud, we can use plain text or ADF format
        # Using plain text is simpler and works well
        payload["fields"]["description"] = description
    
    # Add priority if valid
    if priority and priority.lower() not in ['', 'none', 'default', 'medium']:
        payload["fields"]["priority"] = {
            "name": priority
        }
    
    # Add assignee if provided
    if assignee:
        users = fetch_users()
        user = find_user_by_name(assignee, users)
        if user:
            payload["fields"]["assignee"] = {
                "accountId": user['accountId']
            }
    
    # Add labels
    if labels:
        payload["fields"]["labels"] = labels
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            issue = response.json()
            print(f"✅ Created issue: {issue['key']} - {summary}")
            return issue
        else:
            print(f"❌ Failed to create issue: {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                if 'errors' in error_data:
                    print(f"❌ Field errors: {error_data['errors']}")
                if 'errorMessages' in error_data:
                    print(f"❌ Error messages: {error_data['errorMessages']}")
            except:
                pass
            return None
    except Exception as e:
        print(f"❌ Error creating issue: {e}")
        return None

