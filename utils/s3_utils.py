"""
S3 Utilities for Bug Report Backend
Handles uploading files to S3 bucket.
"""

import os
import boto3
import base64
from typing import Dict, Optional
from datetime import datetime


def get_s3_client() -> Optional[boto3.client]:
    """Get S3 client with credentials from environment variables."""
    try:
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not aws_access_key or not aws_secret_key:
            print("⚠️ AWS credentials not found in environment variables")
            return None
        
        s3_client = boto3.client(
            's3',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        return s3_client
    except Exception as e:
        print(f"❌ Error creating S3 client: {e}")
        return None


def upload_to_s3(
    content: bytes,
    key: str,
    content_type: str = 'text/plain',
    bucket_name: Optional[str] = None
) -> Optional[str]:
    """
    Upload content to S3 bucket.
    
    Args:
        content: Content to upload (bytes)
        key: S3 key (path)
        content_type: Content type (MIME type)
        bucket_name: S3 bucket name (defaults to env var)
    
    Returns:
        S3 URL if successful, None otherwise
    """
    s3_client = get_s3_client()
    if not s3_client:
        return None
    
    bucket = bucket_name or os.getenv('S3_BUCKET_NAME', 'agilow-bug-reports')
    
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        s3_url = f"s3://{bucket}/{key}"
        print(f"✅ Uploaded to S3: {s3_url}")
        return s3_url
    except Exception as e:
        print(f"❌ Error uploading to S3: {e}")
        return None


def upload_text_to_s3(
    text: str,
    key: str,
    bucket_name: Optional[str] = None
) -> Optional[str]:
    """Upload text content to S3."""
    return upload_to_s3(
        content=text.encode('utf-8'),
        key=key,
        content_type='text/plain',
        bucket_name=bucket_name
    )


def upload_base64_to_s3(
    base64_data: str,
    key: str,
    content_type: str = 'application/octet-stream',
    bucket_name: Optional[str] = None
) -> Optional[str]:
    """Upload base64-encoded content to S3."""
    try:
        # Remove data URL prefix if present (e.g., "data:image/png;base64,")
        if ',' in base64_data:
            base64_data = base64_data.split(',')[-1]
        
        content = base64.b64decode(base64_data)
        return upload_to_s3(
            content=content,
            key=key,
            content_type=content_type,
            bucket_name=bucket_name
        )
    except Exception as e:
        print(f"❌ Error decoding base64: {e}")
        return None


def upload_bug_report_attachments(
    report_id: str,
    transcription: Optional[str] = None,
    console_logs: Optional[str] = None,
    screen_recording: Optional[str] = None,
    bucket_name: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """
    Upload all bug report attachments to S3.
    
    Args:
        report_id: Unique report ID
        transcription: Full conversation transcript
        console_logs: Console logs from frontend
        screen_recording: Base64-encoded screen recording or file path
        bucket_name: S3 bucket name
    
    Returns:
        Dictionary of S3 URLs for each uploaded file
    """
    s3_urls = {}
    
    # Upload transcription
    if transcription:
        transcription_key = f"{report_id}/transcription.txt"
        s3_urls['transcription'] = upload_text_to_s3(
            text=transcription,
            key=transcription_key,
            bucket_name=bucket_name
        )
    
    # Upload console logs
    if console_logs:
        console_logs_key = f"{report_id}/console_logs.txt"
        s3_urls['console_logs'] = upload_text_to_s3(
            text=console_logs,
            key=console_logs_key,
            bucket_name=bucket_name
        )
    
    # Upload screen recording
    if screen_recording:
        # Determine if it's base64 or file path
        if screen_recording.startswith('data:') or (len(screen_recording) > 100 and not screen_recording.startswith('/')):
            # Base64 encoded
            screen_recording_key = f"{report_id}/screen_recording.webm"
            s3_urls['screen_recording'] = upload_base64_to_s3(
                base64_data=screen_recording,
                key=screen_recording_key,
                content_type='video/webm',
                bucket_name=bucket_name
            )
        else:
            # File path - read and upload
            try:
                with open(screen_recording, 'rb') as f:
                    content = f.read()
                screen_recording_key = f"{report_id}/screen_recording.webm"
                s3_urls['screen_recording'] = upload_to_s3(
                    content=content,
                    key=screen_recording_key,
                    content_type='video/webm',
                    bucket_name=bucket_name
                )
            except Exception as e:
                print(f"❌ Error reading screen recording file: {e}")
    
    return s3_urls

