# agilow-bug-backend

FastAPI backend for Agilow bug tracking system with a 2-agent architecture:
- **Transcription Agent**: Receives transcriptions and interacts with users
- **Jira Ticket Agent**: Creates tickets in Jira

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your environment variables:
   ```
   OPENAI_API_KEY=your_key_here
   JIRA_URL=your_jira_url
   JIRA_EMAIL=your_email
   JIRA_API_TOKEN=your_token
   ```

3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## Project Structure

```
agilow-bug-backend/
├── agents/          # Agent implementations
│   ├── transcription_agent.py
│   └── jira_ticket_agent.py
├── api/             # API route handlers
├── utils/           # Utility functions
├── main.py          # FastAPI application entry point
└── requirements.txt # Python dependencies
```

## Development

The server will run on `http://localhost:8000` by default.

API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

