# agilow-bug-backend

FastAPI backend for Agilow bug tracking system with a 2-agent architecture:
- **Bug Agent**: Conducts conversation with users to gather comprehensive bug report information
- **Jira Ticket Executor**: Creates Jira tickets from collected bug report data

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your environment variables (see Environment Variables section below)

3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## Environment Variables

Create a `.env` file in the root directory with the following variables:

### Required:
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

### Optional (can also be sent in API requests):
```bash
# Jira Configuration
JIRA_API_KEY=your_jira_api_key_here
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
JIRA_EMAIL=your_email@example.com
```

### Required for S3 Uploads:
```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=agilow-bug-reports
```

## Project Structure

```
agilow-bug-backend/
├── agents/
│   ├── bug_agent.py              # Conversation agent for gathering bug info
│   └── jira_ticket_executor.py   # Creates Jira tickets from bug reports
├── api/
│   ├── bug_report_handler.py     # Coordinates bug report processing
│   └── jira_handler.py           # Jira API operations
├── utils/
│   ├── api_clients.py            # OpenAI client configuration
│   └── s3_utils.py               # S3 upload utilities
├── main.py                        # FastAPI application entry point
└── requirements.txt              # Python dependencies
```

## API Endpoints

### POST `/bug-report-chat`
Main endpoint for bug report conversation.

**Request Body:**
```json
{
  "transcript": "User's message/transcript",
  "session_id": "unique_session_id",
  "user_id": "optional_user_id",
  "console_logs": "optional_console_logs",
  "screen_recording": "optional_base64_screen_recording",
  "conversation_history": [{"role": "user", "content": "..."}],
  "jira_api_key": "optional_jira_api_key",
  "jira_base_url": "optional_jira_base_url",
  "jira_project_key": "optional_jira_project_key",
  "jira_email": "optional_jira_email"
}
```

**Response:**
```json
{
  "success": true,
  "user_response": "Agent's response",
  "bug_report_complete": false,
  "collected_info": {...}
}
```

When bug report is complete:
```json
{
  "success": true,
  "user_response": "Bug report submitted!",
  "bug_report_complete": true,
  "jira_ticket": {
    "success": true,
    "issue_key": "PROJ-123",
    "issue_url": "https://..."
  },
  "s3_urls": {
    "transcription": "s3://...",
    "console_logs": "s3://...",
    "screen_recording": "s3://..."
  }
}
```

### POST `/bug-report-chat/reset`
Reset conversation state for a session.

**Request Body:**
```json
{
  "session_id": "session_id_to_reset"
}
```

## Development

The server will run on `http://localhost:8000` by default.

API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## How It Works

1. **Frontend sends transcript** → `/bug-report-chat` endpoint
2. **Bug Agent** conducts conversation to gather:
   - Bug title/summary
   - Description
   - Steps to reproduce
   - Expected vs Actual behavior
   - Environment info
   - Severity
3. **When complete**, the system:
   - Uploads conversation transcript to S3
   - Uploads console logs to S3
   - Uploads screen recording to S3
   - Creates Jira ticket with all collected information
   - Returns ticket details and S3 URLs

