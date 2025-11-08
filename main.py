from dotenv import load_dotenv
try:
    load_dotenv()
except Exception as e:
    print(f"⚠️ Warning: Could not load .env file: {e}")
    print("⚠️ Continuing without .env file - environment variables will be used directly")

from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

# Import our modules
from agents.bug_agent import generate_bug_report_conversation
from api.bug_report_handler import process_bug_report
from utils.api_clients import get_openai_client

# Conversation state storage (in-memory, can be moved to DB later)
conversation_states: Dict[str, Dict[str, Any]] = {}

# Initialize FastAPI app
app = FastAPI(
    title="Agilow Bug Backend",
    version="1.0.0",
    description="FastAPI backend for Agilow bug tracking with 2-agent system"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "🚀 Agilow Bug Backend is running!",
        "status": "success",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "agilow-bug-backend"
    }


# Pydantic models for request/response
class BugReportChatRequest(BaseModel):
    transcript: str
    session_id: str
    user_id: Optional[str] = None
    console_logs: Optional[str] = None
    screen_recording: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    jira_api_key: Optional[str] = None
    jira_base_url: Optional[str] = None
    jira_project_key: Optional[str] = None
    jira_email: Optional[str] = None


@app.post("/bug-report-chat")
async def bug_report_chat(request: BugReportChatRequest):
    """
    Main endpoint for bug report conversation.
    Handles back-and-forth conversation to gather bug report information,
    then creates Jira ticket and uploads attachments to S3 when complete.
    """
    try:
        session_id = request.session_id
        transcript = request.transcript.strip()
        
        if not transcript:
            raise HTTPException(status_code=400, detail="Transcript cannot be empty")
        
        # Initialize or get conversation state
        if session_id not in conversation_states:
            conversation_states[session_id] = {
                'collected_info': {},
                'conversation_history': [],
                'is_complete': False
            }
        
        state = conversation_states[session_id]
        
        # Update conversation history
        conversation_history = request.conversation_history or state.get('conversation_history', [])
        conversation_history.append({
            'role': 'user',
            'content': transcript
        })
        
        # Get OpenAI client
        openai_client = get_openai_client()
        if not openai_client:
            raise HTTPException(status_code=500, detail="OpenAI client not configured")
        
        # Call Bug Agent
        print(f"[BUG REPORT CHAT] Processing message for session: {session_id}")
        agent_response = generate_bug_report_conversation(
            user_input=transcript,
            conversation_history=conversation_history,
            collected_info=state['collected_info'],
            console_logs=request.console_logs,
            openai_client=openai_client
        )
        
        # Update state with new collected info
        state['collected_info'] = agent_response.get('bug_report_data', {})
        state['is_complete'] = agent_response.get('is_complete', False)
        
        # Add agent response to conversation history
        conversation_history.append({
            'role': 'assistant',
            'content': agent_response.get('user_response', '')
        })
        state['conversation_history'] = conversation_history
        
        # Build full conversation transcript
        full_transcript = "\n".join([
            f"{msg['role'].title()}: {msg['content']}"
            for msg in conversation_history
        ])
        
        # If bug report is complete, process it
        jira_ticket = None
        s3_urls = {}
        if state['is_complete']:
            print(f"[BUG REPORT CHAT] Bug report complete for session: {session_id}")
            
            # Prepare Jira credentials
            jira_credentials = None
            if request.jira_api_key and request.jira_base_url and request.jira_project_key:
                jira_credentials = {
                    'api_key': request.jira_api_key,
                    'base_url': request.jira_base_url,
                    'project_key': request.jira_project_key,
                    'email': request.jira_email
                }
            
            # Process bug report (upload to S3 and create Jira ticket)
            process_result = process_bug_report(
                bug_report_data=state['collected_info'],
                conversation_transcript=full_transcript,
                console_logs=request.console_logs,
                screen_recording=request.screen_recording,
                jira_credentials=jira_credentials,
                user_id=request.user_id
            )
            
            s3_urls = process_result.get('s3_urls', {})
            jira_ticket = process_result.get('jira_ticket')
            
            # Clear conversation state after processing
            del conversation_states[session_id]
        
        # Build response
        response = {
            'success': True,
            'user_response': agent_response.get('user_response', ''),
            'bug_report_complete': state['is_complete'],
            'collected_info': state['collected_info']
        }
        
        if state['is_complete']:
            response['jira_ticket'] = jira_ticket
            response['s3_urls'] = s3_urls
            response['message'] = 'Bug report submitted successfully!'
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BUG REPORT CHAT ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/bug-report-chat/reset")
async def reset_bug_report_session(session_id: str = Body(...)):
    """Reset conversation state for a session."""
    if session_id in conversation_states:
        del conversation_states[session_id]
        return {"success": True, "message": "Session reset successfully"}
    return {"success": False, "message": "Session not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

