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
    
    # Build collected information summary
    collected_summary = _build_collected_info_summary(collected_info)
    
    # Determine what information is still needed
    missing_fields = _get_missing_fields(collected_info)
    
    # Build system prompt
    system_prompt = _build_system_prompt(collected_summary, missing_fields, console_logs)
    
    user_prompt = f"""User Message: "{user_input}"

Current Date: {datetime.now().strftime('%Y-%m-%d')}

Collected Information So Far:
{collected_summary}

Missing Information:
{', '.join(missing_fields) if missing_fields else 'None - all information collected!'}

Console Logs Available: {'Yes' if console_logs else 'No'}

Please analyze this user input and provide a JSON response with the following structure:

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
        "additional_notes": "Any other relevant information"
    }},
    "is_complete": true/false,
    "questions_to_ask": ["question1", "question2"] (if not complete)
}}

CRITICAL GUIDELINES:
1. Extract information from the user's message and update bug_report_data accordingly
2. If information is missing, ask specific questions in user_response
3. Set is_complete to TRUE only when you have:
   - Title (or clear description that can serve as title)
   - Description (what the bug is)
   - Steps to reproduce (or at least what the user was doing)
   - Expected vs Actual behavior (or clear description of the problem)
4. Be conversational and helpful - guide the user through providing complete information
5. If console_logs are available, mention that you'll include them in the bug report
6. Don't mark as complete too early - ensure you have enough detail for a developer to understand and fix the bug
7. Return ONLY valid JSON, no additional text or formatting"""

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
            
            return {
                "user_response": user_response,
                "bug_report_data": updated_collected_info,
                "is_complete": is_complete,
                "questions_to_ask": questions_to_ask
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


def _build_system_prompt(collected_summary: str, missing_fields: List[str], console_logs: Optional[str] = None) -> str:
    """Build the system prompt for the Bug Agent."""
    
    prompt = f"""You are a helpful bug report assistant for Agilow. Your job is to guide users through providing comprehensive bug report information.

**Your Role:**
- Conduct a friendly, conversational interview to gather bug report details
- Ask specific questions to fill in missing information
- Ensure the bug report is complete enough for developers to understand and fix the issue
- Be patient and helpful - users may not know what information is needed

**Information to Collect:**
1. **Title/Summary**: A clear, concise title for the bug
2. **Description**: What the bug is - what went wrong
3. **Steps to Reproduce**: Detailed steps that lead to the bug
4. **Expected Behavior**: What should have happened
5. **Actual Behavior**: What actually happened
6. **Severity**: How critical is this bug? (Critical/High/Medium/Low)
7. **Environment**: Browser, OS, device, version information
8. **Additional Notes**: Any other relevant context

**Current Status:**
Collected Information:
{collected_summary}

Missing Information:
{', '.join(missing_fields) if missing_fields else 'All information collected!'}

**Console Logs:**
{'Console logs are available and will be included in the bug report.' if console_logs else 'No console logs provided yet.'}

**Guidelines:**
- Ask one or two questions at a time - don't overwhelm the user
- Be specific in your questions (e.g., "What browser are you using?" instead of "Tell me about your environment")
- If the user provides partial information, acknowledge it and ask for the rest
- When you have enough information, confirm with the user before marking as complete
- Use natural, conversational language
- Be encouraging and helpful"""
    
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

