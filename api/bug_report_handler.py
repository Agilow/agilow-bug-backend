"""
Bug Report Handler
Coordinates bug report processing, S3 uploads, and Jira ticket creation.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from utils.s3_utils import upload_bug_report_attachments
from agents.jira_ticket_executor import create_bug_report_ticket


def process_bug_report(
    bug_report_data: Dict[str, Any],
    conversation_transcript: str,
    console_logs: Optional[str] = None,
    screen_recording: Optional[str] = None,
    jira_credentials: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a complete bug report: upload to S3 and create Jira ticket.
    
    Args:
        bug_report_data: Collected bug report information
        conversation_transcript: Full conversation transcript
        console_logs: Console logs from frontend
        screen_recording: Screen recording (base64 or file path)
        jira_credentials: Jira credentials for ticket creation
        user_id: User ID for report identification
    
    Returns:
        Dict with success status, S3 URLs, and Jira ticket details
    """
    # Generate unique report ID
    report_id = f"bug_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id or 'anonymous'}"
    
    # Upload attachments to S3
    print(f"[BUG REPORT] Uploading attachments for report: {report_id}")
    s3_urls = upload_bug_report_attachments(
        report_id=report_id,
        transcription=conversation_transcript,
        console_logs=console_logs,
        screen_recording=screen_recording
    )
    
    # Create Jira ticket if credentials provided
    jira_ticket = None
    if jira_credentials:
        print(f"[BUG REPORT] Creating Jira ticket for report: {report_id}")
        jira_ticket = create_bug_report_ticket(
            bug_report_data=bug_report_data,
            jira_credentials=jira_credentials,
            s3_urls=s3_urls
        )
    else:
        print(f"[BUG REPORT] No Jira credentials provided, skipping ticket creation")
    
    return {
        'success': True,
        'report_id': report_id,
        's3_urls': s3_urls,
        'jira_ticket': jira_ticket,
        'message': 'Bug report processed successfully'
    }

