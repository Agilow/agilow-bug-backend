"""
Jira Ticket Executor for Bug Reports
Creates Jira tickets from bug report data collected by Bug Agent.
"""

from typing import Dict, Any, Optional
from api.jira_handler import create_issue, set_jira_credentials


def create_bug_report_ticket(
    bug_report_data: Dict[str, Any],
    jira_credentials: Dict[str, str],
    s3_urls: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a Jira ticket from bug report data.
    
    Args:
        bug_report_data: Dictionary containing bug report information
        jira_credentials: Jira credentials (api_key, base_url, project_key, email)
        s3_urls: Optional dictionary of S3 URLs for attachments
    
    Returns:
        Dict with success status and ticket details
    """
    # Set Jira credentials
    set_jira_credentials(
        api_key=jira_credentials.get('api_key'),
        base_url=jira_credentials.get('base_url'),
        project_key=jira_credentials.get('project_key'),
        email=jira_credentials.get('email')
    )
    
    # Build Jira issue description from bug report data
    description = _build_jira_description(bug_report_data, s3_urls)
    
    # Determine issue type (default to Bug)
    issue_type = bug_report_data.get('issue_type', 'Bug')
    
    # Determine priority from severity
    priority = _map_severity_to_priority(bug_report_data.get('severity', 'Medium'))
    
    # Build issue data
    issue_data = {
        'task': bug_report_data.get('title', 'Bug Report'),
        'description': description,
        'issue_type': issue_type,
        'priority': priority,
        'labels': ['bug-report', 'High']  # Add default labels
    }
    
    # Create the issue
    issue = create_issue(issue_data)
    
    if issue:
        return {
            'success': True,
            'issue_key': issue.get('key'),
            'issue_id': issue.get('id'),
            'issue_url': f"{jira_credentials.get('base_url')}/browse/{issue.get('key')}",
            'summary': issue.get('fields', {}).get('summary', ''),
            'message': f"✅ Bug report created successfully: {issue.get('key')}"
        }
    else:
        return {
            'success': False,
            'error': 'Failed to create Jira ticket',
            'message': '❌ Failed to create bug report ticket in Jira'
        }


def _build_jira_description(bug_report_data: Dict[str, Any], s3_urls: Optional[Dict[str, str]] = None) -> str:
    """Build a formatted Jira description from bug report data."""
    description_parts = []
    
    # Description
    if bug_report_data.get('description'):
        description_parts.append(f"Description:\n{bug_report_data['description']}")
    
    # Steps to Reproduce
    if bug_report_data.get('steps_to_reproduce'):
        description_parts.append(f"Steps to Reproduce:\n{bug_report_data['steps_to_reproduce']}")
    
    # Expected Behavior
    if bug_report_data.get('expected_behavior'):
        description_parts.append(f"Expected Behavior:\n{bug_report_data['expected_behavior']}")
    
    # Actual Behavior
    if bug_report_data.get('actual_behavior'):
        description_parts.append(f"Actual Behavior:\n{bug_report_data['actual_behavior']}")
    
    # Environment
    if bug_report_data.get('environment'):
        description_parts.append(f"Environment:\n{bug_report_data['environment']}")
    
    # Additional Notes
    if bug_report_data.get('additional_notes'):
        description_parts.append(f"Additional Notes:\n{bug_report_data['additional_notes']}")
    
    # Add S3 URLs if available
    if s3_urls:
        description_parts.append("\nAttachments:")
        if s3_urls.get('transcription'):
            description_parts.append(f"- Full conversation transcript: {s3_urls['transcription']}")
        if s3_urls.get('console_logs'):
            description_parts.append(f"- Console logs: {s3_urls['console_logs']}")
        if s3_urls.get('screen_recording'):
            description_parts.append(f"- Screen recording: {s3_urls['screen_recording']}")
    
    return "\n".join(description_parts) if description_parts else "No description provided."


def _map_severity_to_priority(severity: str) -> str:
    """Map bug severity to Jira priority."""
    severity_lower = severity.lower() if severity else 'medium'
    
    mapping = {
        'critical': 'Highest',
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low',
        'lowest': 'Lowest'
    }
    
    return mapping.get(severity_lower, 'Medium')

