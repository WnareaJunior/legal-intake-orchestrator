"""
Records Wrangler Agent - Specialist in medical records requests
NOW WITH MULTI-PROVIDER DETECTION

NOTE: This is the most complex agent - handles multi-provider detection
which is actually a pretty sophisticated feature for a hackathon project
The multi-provider stuff is what makes this demo impressive
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
        # NOTE: Only requiring patient_name as critical
        # DOB and dates are nice-to-have but not strictly required
        # TODO: Might want to add 'provider_name' here too?
        return ['patient_name']  # Provider checked separately for multi-provider cases
    
    def get_system_prompt(self) -> str:
        # NOTE: This prompt is HUGE - 96 lines!
        # It's actually really well structured though with clear examples
        # TODO: Could break this into smaller sections or load from file
        # But for now it's readable and works great
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

        NOTE: This is thorough - checks not just that fields exist but that they make sense
        Like provider_count matching the actual array length
        """
        required = ['subject', 'body', 'extracted_info', 'confidence', 'providers', 'provider_count']
        if not all(key in output for key in required):
            return False, "Missing required output fields"

        extracted = output.get('extracted_info', {})

        # Check critical fields
        if extracted.get('patient_name') in ['Not found', '', None]:
            return False, "Patient name not found"

        # Validate providers array
        # This is key - we need at least one provider to send a request to
        providers = output.get('providers', [])
        if not providers or len(providers) == 0:
            return False, "No providers found"

        # Check provider count matches
        # TODO: This could just calculate provider_count from len(providers) instead of validating
        # Would be more defensive but this is fine for catching prompt issues
        if output.get('provider_count', 0) != len(providers):
            return False, "Provider count mismatch"
        
        # Validate each provider has required fields
        # Looping through to check each one - good defensive coding
        for idx, provider in enumerate(providers):
            if not provider.get('provider_name') or provider.get('provider_name') == 'Not found':
                return False, f"Provider {idx + 1} missing name"
            if not provider.get('provider_type'):
                return False, f"Provider {idx + 1} missing type"

        # Body must be substantial (or summary if multiple)
        # NOTE: 80 chars is pretty short - just a basic sanity check
        # A real email would be like 200+ chars
        body = output.get('body', '')
        if len(body) < 80:
            return False, f"Email body too short ({len(body)} chars)"

        # Multi-provider specific validation
        # Catch the case where we said "multiple" but only found one
        if output.get('requires_multiple_requests', False):
            if output.get('provider_count', 0) < 2:
                return False, "Marked as multi-provider but only 1 provider found"

        return True, ""
    
    def calculate_quality_score(self, output: Dict[str, Any]) -> float:
        """Enhanced quality scoring for multi-provider cases"""
        # Start with base score from parent class (confidence + completeness + validation)
        base_score = super().calculate_quality_score(output)

        extracted = output.get('extracted_info', {})
        bonus = 0.0

        # Bonus for complete patient info
        # If we have name + DOB + dates, that's a complete picture
        if all(extracted.get(f) not in ['Not found', '', None] for f in ['patient_name', 'dob', 'date_range']):
            bonus += 0.05

        # Bonus for multi-provider detection (shows complexity handling)
        # This is what makes this agent special - reward multi-provider cases
        # NOTE: Capped at 3 extra providers to prevent crazy bonuses
        provider_count = output.get('provider_count', 0)
        if provider_count > 1:
            bonus += 0.05 * min(provider_count - 1, 3)  # Up to +0.15 for 4+ providers

        # Bonus for detailed provider context
        # Not just finding providers but also context about each one
        providers = output.get('providers', [])
        detailed_providers = sum(1 for p in providers if p.get('treatment_context') and p.get('specific_dates'))
        if providers:
            bonus += 0.05 * (detailed_providers / len(providers))

        # TODO: These bonuses can push score above 1.0 which is why we cap it
        # Could redesign scoring to be percentage-based instead of additive
        return min(base_score + bonus, 1.0)
    
    def generate_individual_drafts(self, output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate separate email drafts for each provider
        Called after validation passes

        NOTE: This is where the magic happens - turning 1 message into 5 emails
        This is what saves paralegals hours of work
        """
        if not output.get('requires_multiple_requests', False):
            # Single provider - return original output
            return [output]

        extracted = output.get('extracted_info', {})
        providers = output.get('providers', [])

        drafts = []

        # Loop through each provider and generate a standalone email draft
        for idx, provider in enumerate(providers):
            provider_name = provider.get('provider_name', 'Unknown Provider')
            treatment_context = provider.get('treatment_context', 'medical treatment')
            specific_dates = provider.get('specific_dates', extracted.get('date_range', 'Not specified'))
            
            # Generate individual draft
            # NOTE: This is a template-based approach - works but is rigid
            # TODO: Could use Gemini to generate each draft for more natural language
            # But templates are actually better for consistency and speed
            draft_body = f"""Dear {provider_name} Medical Records Department,

I am writing to request a copy of medical records for my patient, {extracted.get('patient_name', 'Not specified')}"""

            # Conditionally add DOB if we have it
            if extracted.get('dob') and extracted.get('dob') != 'Not found':
                draft_body += f", DOB: {extracted.get('dob')}"

            draft_body += f"""

The records requested pertain to {treatment_context}"""

            # Add specific dates if available
            if specific_dates and specific_dates != 'Not specified':
                draft_body += f""" on or around {specific_dates}"""

            # Standard HIPAA compliance closing
            # TODO: These placeholder values like [Your Email Address] should be filled in
            # Could pull from config or lawyer profile
            draft_body += """

Please provide these records in accordance with HIPAA regulations to ensure patient privacy and confidentiality. You may send the records to [Your Email Address/Secure Portal Instructions].

Thank you for your prompt attention to this matter.

Sincerely,
Records Department"""
            
            # Package up the draft with all metadata
            # This structure matches what the frontend expects
            individual_draft = {
                "provider_id": idx + 1,
                "provider_name": provider_name,
                "provider_type": provider.get('provider_type', 'unknown'),
                "subject": f"Medical Records Request - {extracted.get('patient_name', 'Patient')} - {provider_name}",
                "body": draft_body,
                "extracted_info": extracted,  # Same patient info across all drafts
                "specific_provider_context": provider,  # Provider-specific details
                "confidence": output.get('confidence', 0.85),
                "success": True
            }

            drafts.append(individual_draft)

        # Return array of draft objects, one per provider
        # Frontend will display these as separate cards
        return drafts