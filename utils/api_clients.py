"""
API Client Utilities
Provides configured clients for external APIs.
"""

import os
from openai import OpenAI
from typing import Optional


def get_openai_client() -> Optional[OpenAI]:
    """Get configured OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("⚠️ OPENAI_API_KEY not found in environment variables")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        print(f"❌ Error creating OpenAI client: {e}")
        return None

