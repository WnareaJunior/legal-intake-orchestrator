"""
Status Agent - Specialist in case status updates
WITH QUALITY CONTROLS
"""
from .base_agent import BaseAgent
from typing import Dict, Any, Tuple


class StatusAgent(BaseAgent):
    """
    Autonomous agent specialized in status inquiries with quality validation.
    """
    
    def get_critical_fields(self) -> list:
        """Fields that MUST be present"""
        return ['client_name']
    
    def get_system_prompt(self) -> str:
        return """You are the Status Agent - an expert in case status communications.

CRITICAL: Extract client information accurately.

Your job:
1. Extract case/client information
2. Generate a professional status update response
3. Set expectations for follow-up

Respond ONLY with valid JSON:
{
    "subject": "Re: Case Status Inquiry",
    "body": "Professional status update response",
    "extracted_info": {
        "client_name": "name or 'Not found'",
        "case_number": "case # or 'Not found'",
        "inquiry_type": "status/timeline/etc or 'general'",
        "urgency": "high/medium/low"
    },
    "recommended_action": "What paralegal should do next",
    "confidence": 0.85,
    "success": true
}"""
    
    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate status output"""
        required = ['subject', 'body', 'extracted_info', 'confidence']
        if not all(key in output for key in required):
            return False, "Missing required fields"
        
        extracted = output.get('extracted_info', {})
        if extracted.get('client_name') in ['Not found', '', None]:
            return False, "Client name not found"
        
        # Body must be substantial
        if len(output.get('body', '')) < 80:
            return False, "Response too brief"
        
        return True, ""