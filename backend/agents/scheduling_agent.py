"""
Scheduling Agent - Specialist in appointment scheduling
WITH QUALITY CONTROLS

NOTE: This is way simpler than RecordsWranglerAgent
No multi-provider complexity, just straightforward scheduling extraction
"""
from .base_agent import BaseAgent
from typing import Dict, Any, Tuple


class SchedulingAgent(BaseAgent):
    """
    Autonomous agent specialized in scheduling requests with quality validation.
    """

    def get_critical_fields(self) -> list:
        """Fields that MUST be present"""
        # Only need the name - dates/times are nice but we can ask for them
        return ['client_name']  # At minimum need to know who
    
    def get_system_prompt(self) -> str:
        # NOTE: This prompt is much shorter than RecordsWrangler
        # Scheduling is simpler domain - just date/time extraction
        # TODO: Could add timezone handling - that's a common pain point
        return """You are the Scheduling Agent - an expert in appointment coordination.

CRITICAL: Extract client name and scheduling details accurately.

Your job:
1. Extract scheduling details (requested dates/times, type of meeting, duration)
2. Generate a professional response with calendar invite details
3. Offer alternative times if needed

Respond ONLY with valid JSON:
{
    "subject": "Re: Appointment Request",
    "body": "Professional response with meeting details",
    "extracted_info": {
        "requested_date": "extracted date or 'Not specified'",
        "requested_time": "extracted time or 'Not specified'",
        "meeting_type": "consultation/follow-up/etc or 'Not specified'",
        "duration": "estimated duration or 'Not specified'",
        "client_name": "name or 'Not found'"
    },
    "suggested_invite": {
        "title": "Meeting title",
        "date": "Proposed date",
        "time": "Proposed time",
        "duration": "30 minutes"
    },
    "confidence": 0.90,
    "success": true
}"""
    
    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate scheduling output"""
        required = ['subject', 'body', 'extracted_info', 'confidence']
        if not all(key in output for key in required):
            return False, "Missing required fields"

        extracted = output.get('extracted_info', {})
        if extracted.get('client_name') in ['Not found', '', None]:
            return False, "Client name not found"

        # Must have SOME scheduling info - at least one of these
        # NOTE: This is an OR check - pretty lenient
        # As long as we got something scheduling-related, we're good
        has_date = extracted.get('requested_date') not in ['Not specified', '', None]
        has_time = extracted.get('requested_time') not in ['Not specified', '', None]
        has_meeting_type = extracted.get('meeting_type') not in ['Not specified', '', None]

        if not (has_date or has_time or has_meeting_type):
            return False, "No scheduling information found"

        # Body must be substantial (same 80 char check as other agents)
        if len(output.get('body', '')) < 80:
            return False, "Response too brief"

        return True, ""