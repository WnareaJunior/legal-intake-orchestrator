"""
Base Agent Class - All specialist agents inherit from this

NOTE: This is actually really well designed for a hackathon
The abstract base class pattern is perfect here - forces all agents to implement
the same interface while letting them customize their own logic
"""
import google.generativeai as genai
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import json


class BaseAgent(ABC):
    """
    Base class for all specialist agents.
    Each agent has autonomy - it can make decisions, retry, validate.
    Focuses on QUALITY over speed.
    """

    def __init__(self, model_name: str = 'gemini-2.5-flash'):
        # TODO: This creates a new model instance per agent
        # Could share one model across all agents to save memory
        # But for 3 agents it's totally fine, not worth optimizing yet
        self.model = genai.GenerativeModel(model_name)
        self.max_retries = 3  # Increased from 2
        self.agent_name = self.__class__.__name__
        self.min_confidence = 0.85  # Won't proceed if below this
        # TODO: Could make min_confidence configurable per agent type
        # Like records might need 0.90 but status updates could be 0.80
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Each agent defines its own specialized prompt"""
        # NOTE: Making this abstract is smart - forces subclasses to define their prompt
        # TODO: Could add a default implementation that raises NotImplementedError with a helpful message
        pass

    @abstractmethod
    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Each agent validates its own output quality
        Returns: (is_valid, reason_if_invalid)
        """
        # This is the quality guardian pattern - love it
        # Each agent knows what "good" looks like for its domain
        pass

    @abstractmethod
    def get_critical_fields(self) -> list:
        """
        Define which fields are CRITICAL and must be present
        Returns: list of field names that cannot be "Not found"
        """
        # NOTE: Critical fields vary by agent type
        # Records need patient name, scheduling needs dates, etc.
        pass
    
    def process(self, message_text: str) -> Dict[str, Any]:
        """
        Main processing loop - autonomous agent behavior with QUALITY FOCUS
        Tries multiple times, validates rigorously, refuses to proceed if quality too low

        NOTE: This is the core of the whole system - the retry + validation loop
        This pattern is really solid. The agent is truly autonomous here.
        """
        last_error = None
        quality_issues = []

        # TODO: Could add a short-circuit if the first attempt is really bad
        # Like if confidence is below 0.3, maybe don't retry?
        for attempt in range(self.max_retries):
            try:
                # TODO: These print statements are fine for demo but should use logging
                print(f"{self.agent_name}: Attempt {attempt + 1}/{self.max_retries}")

                # Generate output using Gemini
                result = self._call_gemini(message_text, attempt, quality_issues)

                print(f"{self.agent_name}: Got result, validating...")

                # Check confidence threshold FIRST
                # This is smart - no point checking other stuff if confidence is garbage
                confidence = result.get('confidence', 0)
                if confidence < self.min_confidence:
                    issue = f"Confidence too low: {confidence:.2f} < {self.min_confidence}"
                    print(f"{self.agent_name}: ✗ {issue}")
                    quality_issues.append(issue)
                    last_error = issue
                    continue
                
                # Check critical fields
                # This prevents us from generating a draft with "Not found" in key spots
                missing_critical = self._check_critical_fields(result)
                if missing_critical:
                    issue = f"Missing critical fields: {', '.join(missing_critical)}"
                    print(f"{self.agent_name}: ✗ {issue}")
                    quality_issues.append(issue)
                    last_error = issue
                    continue

                # Validate (agent-specific logic)
                # This is where each agent gets to say "this looks good to me"
                is_valid, reason = self.validate_output(result)
                if not is_valid:
                    print(f"{self.agent_name}: ✗ Validation failed: {reason}")
                    quality_issues.append(reason)
                    last_error = reason
                    continue

                # All checks passed!
                # NOTE: We enrich the result with metadata - helpful for debugging
                result['agent'] = self.agent_name
                result['attempt'] = attempt + 1
                result['quality_score'] = self.calculate_quality_score(result)
                result['validation_passed'] = True
                print(f"{self.agent_name}: ✓ Success on attempt {attempt + 1} (Quality: {result['quality_score']:.2f})")
                return result
                
            except json.JSONDecodeError as e:
                # Gemini sometimes returns malformed JSON even though we ask for valid JSON
                # The retry will include this error as feedback which usually fixes it
                print(f"{self.agent_name}: JSON parse error on attempt {attempt + 1}: {e}")
                last_error = f"JSON parse error: {str(e)}"
                quality_issues.append(last_error)
            except Exception as e:
                # Catch-all for API errors, network issues, etc.
                # TODO: Could add exponential backoff here for network errors
                print(f"{self.agent_name}: Error on attempt {attempt + 1}: {e}")
                last_error = str(e)
                quality_issues.append(last_error)

        # All retries failed - REFUSE to proceed
        # This is the "quality guardian" refusing to generate garbage
        # Better to flag for human review than send bad output
        print(f"{self.agent_name}: ✗ QUALITY CHECK FAILED after {self.max_retries} attempts")
        return {
            "agent": self.agent_name,
            "error": last_error,
            "quality_issues": quality_issues,
            "success": False,
            "validation_passed": False,
            "requires_human_review": True,  # This is key - we're explicit about needing help
            "confidence": 0.0
        }
    
    def _check_critical_fields(self, output: Dict[str, Any]) -> list:
        """
        Check if critical fields are missing or marked as "Not found"
        Returns list of missing field names
        """
        # NOTE: This list of "empty" values is hardcoded
        # TODO: Could make this configurable or add more variants like "N/A", "Unknown"
        critical_fields = self.get_critical_fields()
        missing = []

        extracted = output.get('extracted_info', {})
        for field in critical_fields:
            value = extracted.get(field, 'Not found')
            if value in ['Not found', 'Not specified', '', None]:
                missing.append(field)

        return missing
    
    def _call_gemini(self, message_text: str, attempt: int, quality_issues: list) -> Dict[str, Any]:
        """Call Gemini API with agent-specific prompt"""
        system_prompt = self.get_system_prompt()

        # On retry, add previous quality issues as feedback
        # THIS IS GENIUS - we're basically telling the model "you screwed up, here's why, try again"
        # It's like prompt chaining but for quality improvement
        retry_instruction = ""
        if attempt > 0 and quality_issues:
            retry_instruction = f"\n\nIMPORTANT: Previous attempts failed due to:\n"
            for issue in quality_issues[-3:]:  # Last 3 issues
                retry_instruction += f"- {issue}\n"
            retry_instruction += "\nBe MORE THOROUGH. Extract ALL information carefully."

        # TODO: This string concatenation works but could use a template
        full_prompt = f"{system_prompt}{retry_instruction}\n\nMessage:\n{message_text}\n\nJSON Response:"

        # TODO: No timeout set here - if Gemini hangs, we hang
        # Should add timeout parameter to generate_content
        response = self.model.generate_content(full_prompt)
        result_text = response.text.strip()

        # Clean JSON from markdown
        # Same markdown stripping logic as in app.py - should extract to util function
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()

        return json.loads(result_text)
    
    def calculate_quality_score(self, output: Dict[str, Any]) -> float:
        """
        Calculate quality score (0-1) based on:
        - Confidence level (50% weight)
        - Critical fields completeness (30% weight)
        - Validation passing (20% weight)
        Override in subclasses for more specific scoring

        NOTE: These weights are arbitrary but reasonable
        TODO: Could tune these based on what actually matters for lawyers
        Maybe completeness should be higher than confidence?
        """
        score = 0.0

        # Base confidence - 50% of the score
        # This is what Gemini thinks about its own output
        score += output.get('confidence', 0) * 0.5

        # Critical fields completeness - 30% of the score
        # How many required fields did we actually extract?
        critical_fields = self.get_critical_fields()
        if critical_fields:
            extracted = output.get('extracted_info', {})
            found_count = sum(1 for f in critical_fields if extracted.get(f) not in ['Not found', 'Not specified', '', None])
            completeness = found_count / len(critical_fields)
            score += completeness * 0.3

        # Validation passed - 20% bonus
        # Binary: either it passed validation or it didn't
        if output.get('validation_passed', False):
            score += 0.2

        return min(score, 1.0)  # Cap at 1.0 just in case math is off