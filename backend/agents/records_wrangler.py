"""
Records Wrangler Agent - Specialist in medical records requests
NOW WITH MULTI-PROVIDER DETECTION
"""
from .base_agent import BaseAgent
from typing import Dict, Any, Tuple, List


class RecordsWranglerAgent(BaseAgent):
    """
    Autonomous agent specialized in drafting medical records requests.
    - Extracts patient information with STRICT validation
    - DETECTS MULTIPLE PROVIDERS in single message
    - Validates HIPAA compliance
    - Generates separate drafts for each provider
    - REFUSES to proceed if critical data missing
    """
    
    def get_critical_fields(self) -> list:
        """Fields that MUST be present for a valid records request"""
        return ['patient_name']  # Provider checked separately for multi-provider cases
    
    def get_system_prompt(self) -> str:
        return """You are the Records Wrangler Agent - an expert in medical records requests.

CRITICAL NEW CAPABILITY: Detect MULTIPLE medical providers in a single message.

Your job:
1. Extract patient information (name, DOB, dates)
2. **DETECT ALL PROVIDERS mentioned** - there may be multiple hospitals, doctors, clinics
3. For EACH provider, prepare separate request details
4. Draft professional, HIPAA-compliant emails

MULTI-PROVIDER DETECTION:
- Look for multiple hospital names (Orlando Health, Florida Hospital, etc.)
- Look for multiple doctor names (Dr. Smith, Dr. Patel, etc.)
- Look for phrases like "then I went to...", "also saw...", "transferred to..."
- Each provider needs a separate records request

IMPORTANT: 
- If multiple providers found, return ARRAY of provider objects
- Each provider object should have its own draft
- Patient info is shared across all requests
- Be confident (0.85+) only if you found patient name

Respond ONLY with valid JSON:
{
    "subject": "Medical Records Request - [Patient Name]",
    "body": "Full professional email text (or description if multiple providers)",
    "extracted_info": {
        "patient_name": "extracted name or 'Not found'",
        "dob": "date or 'Not found'",
        "date_range": "dates or 'Not found'"
    },
    "providers": [
        {
            "provider_name": "Orlando Health",
            "provider_type": "hospital|doctor|clinic",
            "treatment_context": "ER visit for car accident",
            "specific_dates": "May 15, 2024"
        }
    ],
    "provider_count": 1,
    "requires_multiple_requests": false,
    "confidence": 0.95,
    "success": true
}

If multiple providers detected:
{
    "subject": "Multiple Medical Records Requests - [Patient Name]",
    "body": "Summary: [X] providers detected, [X] separate requests will be generated",
    "extracted_info": {
        "patient_name": "John Doe",
        "dob": "3/20/1985",
        "date_range": "May-June 2024"
    },
    "providers": [
        {
            "provider_name": "Orlando Health",
            "provider_type": "hospital",
            "treatment_context": "Initial ER treatment",
            "specific_dates": "May 15, 2024"
        },
        {
            "provider_name": "Dr. Patel",
            "provider_type": "doctor",
            "treatment_context": "Follow-up orthopedic care",
            "specific_dates": "May 20, 2024"
        }
    ],
    "provider_count": 2,
    "requires_multiple_requests": true,
    "confidence": 0.92,
    "success": true
}"""
    
    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Enhanced validation for multi-provider cases
        """
        required = ['subject', 'body', 'extracted_info', 'confidence', 'providers', 'provider_count']
        if not all(key in output for key in required):
            return False, "Missing required output fields"
        
        extracted = output.get('extracted_info', {})
        
        # Check critical fields
        if extracted.get('patient_name') in ['Not found', '', None]:
            return False, "Patient name not found"
        
        # Validate providers array
        providers = output.get('providers', [])
        if not providers or len(providers) == 0:
            return False, "No providers found"
        
        # Check provider count matches
        if output.get('provider_count', 0) != len(providers):
            return False, "Provider count mismatch"
        
        # Validate each provider has required fields
        for idx, provider in enumerate(providers):
            if not provider.get('provider_name') or provider.get('provider_name') == 'Not found':
                return False, f"Provider {idx + 1} missing name"
            if not provider.get('provider_type'):
                return False, f"Provider {idx + 1} missing type"
        
        # Body must be substantial (or summary if multiple)
        body = output.get('body', '')
        if len(body) < 80:
            return False, f"Email body too short ({len(body)} chars)"
        
        # Multi-provider specific validation
        if output.get('requires_multiple_requests', False):
            if output.get('provider_count', 0) < 2:
                return False, "Marked as multi-provider but only 1 provider found"
        
        return True, ""
    
    def calculate_quality_score(self, output: Dict[str, Any]) -> float:
        """Enhanced quality scoring for multi-provider cases"""
        base_score = super().calculate_quality_score(output)
        
        extracted = output.get('extracted_info', {})
        bonus = 0.0
        
        # Bonus for complete patient info
        if all(extracted.get(f) not in ['Not found', '', None] for f in ['patient_name', 'dob', 'date_range']):
            bonus += 0.05
        
        # Bonus for multi-provider detection (shows complexity handling)
        provider_count = output.get('provider_count', 0)
        if provider_count > 1:
            bonus += 0.05 * min(provider_count - 1, 3)  # Up to +0.15 for 4+ providers
        
        # Bonus for detailed provider context
        providers = output.get('providers', [])
        detailed_providers = sum(1 for p in providers if p.get('treatment_context') and p.get('specific_dates'))
        if providers:
            bonus += 0.05 * (detailed_providers / len(providers))
        
        return min(base_score + bonus, 1.0)
    
    def generate_individual_drafts(self, output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate separate email drafts for each provider
        Called after validation passes
        """
        if not output.get('requires_multiple_requests', False):
            # Single provider - return original output
            return [output]
        
        extracted = output.get('extracted_info', {})
        providers = output.get('providers', [])
        
        drafts = []
        
        for idx, provider in enumerate(providers):
            provider_name = provider.get('provider_name', 'Unknown Provider')
            treatment_context = provider.get('treatment_context', 'medical treatment')
            specific_dates = provider.get('specific_dates', extracted.get('date_range', 'Not specified'))
            
            # Generate individual draft
            draft_body = f"""Dear {provider_name} Medical Records Department,

I am writing to request a copy of medical records for my patient, {extracted.get('patient_name', 'Not specified')}"""
            
            if extracted.get('dob') and extracted.get('dob') != 'Not found':
                draft_body += f", DOB: {extracted.get('dob')}"
            
            draft_body += f"""

The records requested pertain to {treatment_context}"""
            
            if specific_dates and specific_dates != 'Not specified':
                draft_body += f""" on or around {specific_dates}"""
            
            draft_body += """

Please provide these records in accordance with HIPAA regulations to ensure patient privacy and confidentiality. You may send the records to [Your Email Address/Secure Portal Instructions].

Thank you for your prompt attention to this matter.

Sincerely,
Records Department"""
            
            individual_draft = {
                "provider_id": idx + 1,
                "provider_name": provider_name,
                "provider_type": provider.get('provider_type', 'unknown'),
                "subject": f"Medical Records Request - {extracted.get('patient_name', 'Patient')} - {provider_name}",
                "body": draft_body,
                "extracted_info": extracted,
                "specific_provider_context": provider,
                "confidence": output.get('confidence', 0.85),
                "success": True
            }
            
            drafts.append(individual_draft)
        
        return drafts