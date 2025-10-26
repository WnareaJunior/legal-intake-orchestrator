"""
Records Wrangler Agent - Specialist in medical records requests
NOW WITH STRICT QUALITY CONTROLS
"""
from .base_agent import BaseAgent
from typing import Dict, Any, Tuple


class RecordsWranglerAgent(BaseAgent):
    """
    Autonomous agent specialized in drafting medical records requests.
    - Extracts patient information with STRICT validation
    - Validates HIPAA compliance
    - Generates professional drafts
    - REFUSES to proceed if critical data missing
    """
    
    def get_critical_fields(self) -> list:
        """Fields that MUST be present for a valid records request"""
        return ['patient_name', 'provider']  # DOB and date_range nice to have but not critical
    
    def get_system_prompt(self) -> str:
        return """You are the Records Wrangler Agent - an expert in medical records requests.

CRITICAL: You must extract ALL available information accurately. Missing data causes case delays.

Your job:
1. Extract patient information (name, DOB, provider, dates) - BE THOROUGH
2. Draft a professional, HIPAA-compliant email to medical provider
3. Ensure all required fields are present

Requirements:
- Professional tone
- Include patient identifying information
- Specify date range clearly
- Reference HIPAA regulations
- Professional closing

IMPORTANT: 
- If you cannot find patient name, set confidence to 0.4 or lower
- If you cannot find provider, set confidence to 0.5 or lower
- Only use "Not found" if truly absent from message
- Be confident (0.85+) only if you found ALL critical info

Respond ONLY with valid JSON:
{
    "subject": "Medical Records Request - [Patient Name]",
    "body": "Full professional email text",
    "extracted_info": {
        "patient_name": "extracted name or 'Not found'",
        "dob": "date or 'Not found'",
        "provider": "provider name or 'Not found'",
        "date_range": "dates or 'Not found'"
    },
    "confidence": 0.95,
    "success": true
}"""
    
    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Agent validates its own work - autonomous decision making
        Returns (is_valid, reason_if_invalid)
        """
        # Must have these fields in output
        required = ['subject', 'body', 'extracted_info', 'confidence']
        if not all(key in output for key in required):
            return False, "Missing required output fields"
        
        extracted = output.get('extracted_info', {})
        
        # Check critical fields (already done in base class, but double-check)
        if extracted.get('patient_name') in ['Not found', '', None]:
            return False, "Patient name not found"
        if extracted.get('provider') in ['Not found', '', None]:
            return False, "Provider not found"
        
        # Email must be substantial
        body = output.get('body', '')
        if len(body) < 100:
            return False, f"Email body too short ({len(body)} chars)"
        
        # Must mention HIPAA or medical records (basic compliance check)
        body_lower = body.lower()
        if 'hipaa' not in body_lower and 'medical record' not in body_lower:
            return False, "Missing HIPAA reference or medical records mention"
        
        # Subject must include patient name
        subject = output.get('subject', '')
        patient_name = extracted.get('patient_name', '')
        if patient_name != 'Not found' and patient_name.lower() not in subject.lower():
            return False, "Patient name not in subject line"
        
        return True, ""
    
    def calculate_quality_score(self, output: Dict[str, Any]) -> float:
        """Enhanced quality scoring for records requests"""
        base_score = super().calculate_quality_score(output)
        
        # Bonus points for completeness
        extracted = output.get('extracted_info', {})
        bonus = 0.0
        
        # All 4 fields found
        if all(extracted.get(f) not in ['Not found', '', None] for f in ['patient_name', 'dob', 'provider', 'date_range']):
            bonus += 0.1
        
        # Professional language check
        body = output.get('body', '')
        if len(body) > 200 and 'thank you' in body.lower():
            bonus += 0.05
        
        return min(base_score + bonus, 1.0)