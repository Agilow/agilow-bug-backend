from dotenv import load_dotenv
import os

try:
    result = load_dotenv()
    if result:
        print("✅ .env file loaded successfully")
        # Debug: Check if Jira variables are loaded (without showing values)
        jira_vars = {
            'JIRA_API_KEY': 'SET' if os.getenv('JIRA_API_KEY') else 'NOT SET',
            'JIRA_BASE_URL': 'SET' if os.getenv('JIRA_BASE_URL') else 'NOT SET',
            'JIRA_PROJECT_KEY': 'SET' if os.getenv('JIRA_PROJECT_KEY') else 'NOT SET',
            'JIRA_EMAIL': 'SET' if os.getenv('JIRA_EMAIL') else 'NOT SET'
        }
        print(f"📋 Jira environment variables status: {jira_vars}")
    else:
        print("⚠️ .env file not found or empty")
except Exception as e:
    print(f"⚠️ Warning: Could not load .env file: {e}")
    print("⚠️ Continuing without .env file - environment variables will be used directly")

from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

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
class Message(BaseModel):
    id: int
    sender: str  # "user" or "ai"
    text: str

class BugReportChatRequest(BaseModel):
    # Accept either the new format (messages array) or old format (transcript)
    messages: Optional[List[Message]] = None
    transcript: Optional[str] = None  # For backward compatibility
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
    session_id = request.session_id
    
    # Log incoming request data
    print(f"\n{'='*80}")
    print(f"[BUG REPORT CHAT] Received request for session: {session_id}")
    print(f"[BUG REPORT CHAT] Request data:")
    print(f"  - Session ID: {session_id}")
    print(f"  - User ID: {request.user_id}")
    print(f"  - Messages count: {len(request.messages) if request.messages else 0}")
    print(f"  - Transcript: {request.transcript[:100] + '...' if request.transcript and len(request.transcript) > 100 else request.transcript}")
    print(f"  - Console logs: {'Provided' if request.console_logs else 'Not provided'}")
    print(f"  - Screen recording: {'Provided' if request.screen_recording else 'Not provided'}")
    
    if request.messages:
        print(f"  - Messages array:")
        for i, msg in enumerate(request.messages):
            text_preview = msg.text[:100] + '...' if len(msg.text) > 100 else msg.text
            print(f"    [{i+1}] {msg.sender}: {text_preview}")
    else:
        print(f"  - Using transcript format (legacy)")
    
    # Log full request payload in JSON format (for debugging)
    try:
        request_dict = {
            "session_id": request.session_id,
            "user_id": request.user_id,
            "messages": [
                {"id": msg.id, "sender": msg.sender, "text": msg.text}
                for msg in (request.messages or [])
            ] if request.messages else None,
            "transcript": request.transcript,
            "console_logs": request.console_logs[:200] + "..." if request.console_logs and len(request.console_logs) > 200 else request.console_logs,
            "screen_recording": "Provided" if request.screen_recording else None,
            "jira_api_key": "Provided" if request.jira_api_key else None,
            "jira_base_url": request.jira_base_url,
            "jira_project_key": request.jira_project_key,
            "jira_email": request.jira_email
        }
        print(f"[BUG REPORT CHAT] Full request payload (JSON):")
        print(json.dumps(request_dict, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[BUG REPORT CHAT] Error logging request payload: {e}")
    
    print(f"{'='*80}\n")
    
    try:
        
        # Handle both new format (messages array) and old format (transcript)
        if request.messages:
            # New format: messages array with {id, sender, text}
            # Get the latest user message
            user_messages = [msg for msg in request.messages if msg.sender == "user"]
            if not user_messages:
                raise HTTPException(status_code=400, detail="No user messages found in messages array")
            
            # Get the latest user message text
            transcript = user_messages[-1].text.strip()
            
            # Convert messages format to conversation_history format
            conversation_history = []
            for msg in request.messages:
                # Map "user" -> "user", "ai" -> "assistant"
                role = "user" if msg.sender == "user" else "assistant"
                conversation_history.append({
                    'role': role,
                    'content': msg.text
                })
        elif request.transcript:
            # Old format: single transcript string
            transcript = request.transcript.strip()
            conversation_history = request.conversation_history or []
            conversation_history.append({
                'role': 'user',
                'content': transcript
            })
        else:
            raise HTTPException(status_code=400, detail="Either 'messages' or 'transcript' must be provided")
        
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
        
        # Update conversation history (merge with existing if needed)
        if request.messages:
            # For new format, replace with the full conversation from messages
            state['conversation_history'] = conversation_history
            
            # If we have a full conversation history, extract collected info from previous interactions
            # This ensures the agent knows what information has already been gathered
            if len(conversation_history) > 2:  # More than just the current user message
                print(f"[BUG REPORT CHAT] Full conversation history detected ({len(conversation_history)} messages). Analyzing to extract collected info...")
                
                # Get all previous messages (excluding the current one we're processing)
                previous_history = conversation_history[:-1]
                
                # If we have previous AI responses, the last one should contain the collected info summary
                # Otherwise, we need to analyze the conversation to extract what's been collected
                if previous_history:
                    # Get the last AI response to see what was collected
                    prev_ai_messages = [msg for msg in previous_history if msg['role'] == 'assistant']
                    if prev_ai_messages:
                        # The bug agent should have been tracking collected_info in previous responses
                        # We'll extract it by analyzing the conversation
                        # For now, let's call the bug agent with the previous conversation to get collected_info
                        temp_openai_client = get_openai_client()
                        if temp_openai_client:
                            # Get the last user message before the current one
                            prev_user_messages = [msg for msg in previous_history if msg['role'] == 'user']
                            if prev_user_messages:
                                prev_user_input = prev_user_messages[-1]['content']
                                # Analyze previous conversation to extract collected info
                                # This is a lightweight call just to get the collected_info state
                                temp_agent_response = generate_bug_report_conversation(
                                    user_input=prev_user_input,
                                    conversation_history=previous_history,
                                    collected_info=state['collected_info'],  # Start with existing
                                    console_logs=request.console_logs,
                                    openai_client=temp_openai_client
                                )
                                # Update collected_info from the analysis
                                extracted_info = temp_agent_response.get('bug_report_data', {})
                                # Merge with existing collected_info (don't overwrite, merge)
                                for key, value in extracted_info.items():
                                    if value and str(value).strip():  # Only update if value is not empty
                                        state['collected_info'][key] = value
                                print(f"[BUG REPORT CHAT] Extracted collected info from conversation history:")
                                print(json.dumps(state['collected_info'], indent=2, ensure_ascii=False))
        else:
            # For old format, append to existing
            existing_history = state.get('conversation_history', [])
            existing_history.append({
                'role': 'user',
                'content': transcript
            })
            conversation_history = existing_history
        
        # Get OpenAI client
        openai_client = get_openai_client()
        if not openai_client:
            raise HTTPException(status_code=500, detail="OpenAI client not configured")
        
        # Call Bug Agent with the full conversation and updated collected_info
        print(f"[BUG REPORT CHAT] Processing message for session: {session_id}")
        print(f"[BUG REPORT CHAT] Conversation history length: {len(conversation_history)}")
        print(f"[BUG REPORT CHAT] Current collected_info: {json.dumps(state['collected_info'], indent=2, ensure_ascii=False)}")
        agent_response = generate_bug_report_conversation(
            user_input=transcript,
            conversation_history=conversation_history,
            collected_info=state['collected_info'],
            console_logs=request.console_logs,
            openai_client=openai_client
        )
        
        # Log agent response in JSON format
        print(f"[BUG REPORT CHAT] Agent response (JSON):")
        print(json.dumps(agent_response, indent=2, ensure_ascii=False))
        
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
            
            # Prepare Jira credentials (from request or environment variables)
            jira_credentials = None
            
            # Try to get credentials from request first
            jira_api_key = request.jira_api_key
            jira_base_url = request.jira_base_url
            jira_project_key = request.jira_project_key
            jira_email = request.jira_email
            
            # Fall back to environment variables if not provided in request
            if not jira_api_key:
                jira_api_key = os.getenv("JIRA_API_KEY")
                print(f"[BUG REPORT CHAT] Using JIRA_API_KEY from environment: {'SET' if jira_api_key else 'NOT SET'}")
            if not jira_base_url:
                jira_base_url = os.getenv("JIRA_BASE_URL")
                print(f"[BUG REPORT CHAT] Using JIRA_BASE_URL from environment: {'SET' if jira_base_url else 'NOT SET'}")
            if not jira_project_key:
                jira_project_key = os.getenv("JIRA_PROJECT_KEY")
                print(f"[BUG REPORT CHAT] Using JIRA_PROJECT_KEY from environment: {'SET' if jira_project_key else 'NOT SET'}")
            if not jira_email:
                jira_email = os.getenv("JIRA_EMAIL")
                print(f"[BUG REPORT CHAT] Using JIRA_EMAIL from environment: {'SET' if jira_email else 'NOT SET'}")
            
            # Set credentials if we have the required fields
            if jira_api_key and jira_base_url and jira_project_key:
                jira_credentials = {
                    'api_key': jira_api_key,
                    'base_url': jira_base_url,
                    'project_key': jira_project_key,
                    'email': jira_email
                }
                print(f"[BUG REPORT CHAT] Jira credentials configured: Base URL={jira_base_url}, Project={jira_project_key}")
            else:
                missing = []
                if not jira_api_key:
                    missing.append("JIRA_API_KEY")
                if not jira_base_url:
                    missing.append("JIRA_BASE_URL")
                if not jira_project_key:
                    missing.append("JIRA_PROJECT_KEY")
                print(f"[BUG REPORT CHAT] Missing Jira credentials: {', '.join(missing)}")
            
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
        
        # Build response in format compatible with frontend
        ai_response_text = agent_response.get('user_response', '')
        
        response = {
            'success': True,
            'user_response': ai_response_text,  # Keep for backward compatibility
            'message': {  # New format matching frontend structure
                'id': len(conversation_history),
                'sender': 'ai',
                'text': ai_response_text
            },
            'bug_report_complete': state['is_complete'],
            'collected_info': state['collected_info']
        }
        
        if state['is_complete']:
            response['jira_ticket'] = jira_ticket
            response['s3_urls'] = s3_urls
            response['status_message'] = 'Bug report submitted successfully!'  # Changed from 'message' to avoid conflict
        
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

