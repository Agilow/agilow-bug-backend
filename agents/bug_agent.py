"""
Bug Agent for Agilow Bug Backend
Conducts conversation with user to gather comprehensive bug report information.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from openai import OpenAI


def generate_bug_report_conversation(
    user_input: str,
    conversation_history: List[Dict[str, str]],
    collected_info: Dict[str, Any],
    console_logs: Optional[str] = None,
    openai_client: Optional[OpenAI] = None
) -> Dict[str, Any]:
    """
    Generate bug report conversation response and determine if bug report is complete.
    
    Args:
        user_input: The user's message/transcript
        conversation_history: Recent conversation history
        collected_info: Dictionary of information already collected
        console_logs: Console logs from frontend (optional)
        openai_client: OpenAI client instance
    
    Returns:
        Dict with user_response, bug_report_data, and is_complete
    """
    if not openai_client:
        raise ValueError("OpenAI client is required")
    
    # Build conversation context
    conversation_context = _build_conversation_context(conversation_history)
    
    # Count how many questions have been asked (by counting assistant messages)
    questions_asked_count = len([msg for msg in conversation_history if msg.get('role') == 'assistant'])
    
    # Build system prompt with new BugReporter prompt
    system_prompt = _build_system_prompt(console_logs, questions_asked_count)
    
    # Build collected information summary
    collected_summary = _build_collected_info_summary(collected_info)
    
    user_prompt = f"""User Message: "{user_input}"

Current Date: {datetime.now().strftime('%Y-%m-%d')}

Conversation History:
{conversation_context}

Collected Information So Far:
{collected_summary}

Console Logs:
{console_logs if console_logs else 'No console logs provided'}

Questions Asked So Far: {questions_asked_count} (Maximum: 2)

Please analyze this user input and provide a JSON response. ALWAYS STRICTLY OUTPUT IN JSON FORMAT USING THE TEMPLATE BELOW:

{{
    "user_response": "Your conversational response to the user (ask questions to gather missing info or confirm details)",
    "bug_report_data": {{
        "title": "Bug title/summary (if mentioned)",
        "description": "Detailed description of the bug (if provided)",
        "steps_to_reproduce": "Steps to reproduce the bug (if provided)",
        "expected_behavior": "What should have happened (if provided)",
        "actual_behavior": "What actually happened (if provided)",
        "severity": "Critical/High/Medium/Low (if mentioned)",
        "environment": "Browser, OS, device info (if provided)",
        "additional_notes": "Any other relevant information",
        "label": "Critical/High/Medium/Low (if mentioned)"
    }},
    "is_complete": true/false,
    "questions_to_ask": ["Q1: question1", "Q2: question2"]
}}

CRITICAL RULES:
1. Extract information from the user's message and update bug_report_data accordingly
2. Focus on the 5 critical debugging questions: Reproduction Steps, Severity, Expected vs Actual, Recurrence, Restart Behavior
3. Ask at most 2 follow-up questions total. If you've already asked {questions_asked_count} questions, you can ask at most {2 - questions_asked_count} more questions
4. Only mark is_complete: true when user has answered at most 2 follow-up questions OR when you have all 5 critical pieces of information
5. Format questions in questions_to_ask as numbered: "Q1: question text", "Q2: question text"
6. Use console logs if provided to validate or supplement the user's report
7. Speak in a friendly, concise, and clear tone
8. Ask only for missing or ambiguous info - don't repeat questions already answered
9. Return ONLY valid JSON, no additional text or formatting"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        response_text = response.choices[0].message.content
        
        # Parse JSON response
        try:
            cleaned_response = response_text.strip()
            
            # Remove markdown code blocks if present
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            # Find JSON object
            start_idx = cleaned_response.find('{')
            end_idx = cleaned_response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                cleaned_response = cleaned_response[start_idx:end_idx+1]
            
            parsed_response = json.loads(cleaned_response)
            
            user_response = parsed_response.get('user_response', '')
            bug_report_data = parsed_response.get('bug_report_data', {})
            is_complete = parsed_response.get('is_complete', False)
            questions_to_ask = parsed_response.get('questions_to_ask', [])
            
            # Merge new data into collected_info
            updated_collected_info = {**collected_info}
            for key, value in bug_report_data.items():
                if value and value.strip():  # Only update if value is not empty
                    updated_collected_info[key] = value
            
            # Ensure questions_to_ask are properly formatted with Q1:, Q2: prefixes
            formatted_questions = []
            for i, question in enumerate(questions_to_ask, 1):
                question_text = str(question).strip()
                # Remove existing Q1:, Q2: if present and re-add
                if question_text.startswith(f"Q{i}:"):
                    formatted_questions.append(question_text)
                elif question_text.startswith("Q") and ":" in question_text:
                    # Remove old numbering
                    question_text = question_text.split(":", 1)[1].strip()
                    formatted_questions.append(f"Q{i}: {question_text}")
                else:
                    formatted_questions.append(f"Q{i}: {question_text}")
            
            return {
                "user_response": user_response,
                "bug_report_data": updated_collected_info,
                "is_complete": is_complete,
                "questions_to_ask": formatted_questions
            }
            
        except json.JSONDecodeError as e:
            print(f"[BUG AGENT ERROR] Failed to parse JSON: {e}")
            print(f"[BUG AGENT ERROR] Response was: {response_text[:200]}...")
            return {
                "user_response": "I'm having trouble processing that. Could you please rephrase?",
                "bug_report_data": collected_info,
                "is_complete": False,
                "questions_to_ask": []
            }
        
    except Exception as e:
        print(f"[BUG AGENT ERROR] Error in bug agent: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "user_response": "I apologize, but I'm having trouble processing your request right now. Could you please try again?",
            "bug_report_data": collected_info,
            "is_complete": False,
            "questions_to_ask": [],
            "error": str(e)
        }


def _build_system_prompt(console_logs: Optional[str] = None, questions_asked_count: int = 0) -> str:
    """Build the system prompt for BugReporter agent."""
    
    console_logs_note = ""
    if console_logs:
        console_logs_note = f"""
**Console Logs Available:**
{console_logs[:500]}... (truncated for prompt, full logs will be included in bug report)
"""
    
    prompt = f"""You are BugReporter, a voice-first debugging assistant embedded into a mobile app. Your role is to collect all the key information a developer needs to investigate and resolve a reported bug. The user will speak to you naturally. Your job is to extract answers to five critical questions needed for debugging, using the transcript and any back-end console logs provided.

**Your Objectives:**

Extract or clarify answers to these 5 critical debugging questions:

1. **Reproduction Steps**: How did the user reach the current state of the bug?
2. **Severity**: How severe is the bug? Is it blocking progress? (Categorize as High, Medium, or Low)
3. **Expected vs Actual**: What was the user expecting to happen? What actually happened?
4. **Recurrence**: Is this the first time the user has seen this bug?
5. **Restart Behavior**: Did the user try restarting the app to rule out transient issues (like network or environment problems)?

{console_logs_note}

**Engage conversationally**: If any of the 5 key questions are not fully answered from the transcript, ask simple and focused follow-up questions until all required information is complete.

• Ask at most 2 follow up questions total, and then move to create the bug report.
• Questions asked so far: {questions_asked_count} / 2

**Output Format:**

After every user interaction or agent response, return a structured JSON output in the format below. This trace is used to monitor progress, route tasks to downstream agents, and ensure all critical information is captured.

• ALWAYS STRICTLY OUTPUT IN JSON FORMAT USING THE TEMPLATE BELOW:

{{
    "user_response": "Your conversational response to the user (ask questions to gather missing info or confirm details)",
    "bug_report_data": {{
        "title": "Bug title/summary (if mentioned)",
        "description": "Detailed description of the bug (if provided)",
        "steps_to_reproduce": "Steps to reproduce the bug (if provided)",
        "expected_behavior": "What should have happened (if provided)",
        "actual_behavior": "What actually happened (if provided)",
        "severity": "Critical/High/Medium/Low (if mentioned)",
        "environment": "Browser, OS, device info (if provided)",
        "additional_notes": "Any other relevant information",
        "label": "Critical/High/Medium/Low (if mentioned)"
    }},
    "is_complete": true/false,
    "questions_to_ask": ["Q1: question1", "Q2: question2"]
}}

The questions asked within "questions_to_ask" should always be in numbered bullet points (e.g., Q1:, Q2:) and well-spaced out for easy readability.

Only mark is_complete: true when user answers at most 2 follow up questions. If information is missing or unclear, update questions_to_ask with targeted follow-up questions. Since you only have 2 follow up questions, reflect and ask good, sharp questions.

**Behavior Guidelines:**

- Speak in a friendly, concise, and clear tone—this is a mobile user reporting a frustrating issue.
- Ask only for missing or ambiguous info. Don't repeat questions that are already answered clearly.
- Use conversational prompts like:
  - "Got it—can I quickly ask, have you seen this issue before?"
  - "Just to clarify—did you already try restarting the app?"
- Avoid technical jargon unless the user initiates it.
- Assume the user might not be technical—translate any developer requirements into user-friendly questions.

**Inputs You Might Receive:**

- A user transcript (natural spoken language)
- Optionally, console logs from the mobile app backend"""
    
    return prompt


def _build_conversation_context(conversation_history: List[Dict[str, str]]) -> str:
    """Build conversation context from recent history."""
    if not conversation_history:
        return "No previous conversation."
    
    context_parts = []
    for msg in conversation_history[-10:]:  # Last 10 messages
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        context_parts.append(f"{role.title()}: {content}")
    
    return "\n".join(context_parts)


def _build_collected_info_summary(collected_info: Dict[str, Any]) -> str:
    """Build a summary of collected information."""
    if not collected_info:
        return "No information collected yet."
    
    summary_parts = []
    for key, value in collected_info.items():
        if value and str(value).strip():
            summary_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
    
    return "\n".join(summary_parts) if summary_parts else "No information collected yet."


def _get_missing_fields(collected_info: Dict[str, Any]) -> List[str]:
    """Determine what fields are still missing."""
    required_fields = {
        'title': 'Title/Summary',
        'description': 'Description',
        'steps_to_reproduce': 'Steps to Reproduce',
        'expected_behavior': 'Expected Behavior',
        'actual_behavior': 'Actual Behavior'
    }
    
    missing = []
    for field, display_name in required_fields.items():
        value = collected_info.get(field, '')
        if not value or not str(value).strip():
            missing.append(display_name)
    
    return missing

