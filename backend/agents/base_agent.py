"""
Base Agent Class - All specialist agents inherit from this
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
        self.model = genai.GenerativeModel(model_name)
        self.max_retries = 3  # Increased from 2
        self.agent_name = self.__class__.__name__
        self.min_confidence = 0.85  # Won't proceed if below this
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Each agent defines its own specialized prompt"""
        pass
    
    @abstractmethod
    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Each agent validates its own output quality
        Returns: (is_valid, reason_if_invalid)
        """
        pass
    
    @abstractmethod
    def get_critical_fields(self) -> list:
        """
        Define which fields are CRITICAL and must be present
        Returns: list of field names that cannot be "Not found"
        """
        pass
    
    def process(self, message_text: str) -> Dict[str, Any]:
        """
        Main processing loop - autonomous agent behavior with QUALITY FOCUS
        Tries multiple times, validates rigorously, refuses to proceed if quality too low
        """
        last_error = None
        quality_issues = []
        
        for attempt in range(self.max_retries):
            try:
                print(f"{self.agent_name}: Attempt {attempt + 1}/{self.max_retries}")
                
                # Generate output using Gemini
                result = self._call_gemini(message_text, attempt, quality_issues)
                
                print(f"{self.agent_name}: Got result, validating...")
                
                # Check confidence threshold FIRST
                confidence = result.get('confidence', 0)
                if confidence < self.min_confidence:
                    issue = f"Confidence too low: {confidence:.2f} < {self.min_confidence}"
                    print(f"{self.agent_name}: ✗ {issue}")
                    quality_issues.append(issue)
                    last_error = issue
                    continue
                
                # Check critical fields
                missing_critical = self._check_critical_fields(result)
                if missing_critical:
                    issue = f"Missing critical fields: {', '.join(missing_critical)}"
                    print(f"{self.agent_name}: ✗ {issue}")
                    quality_issues.append(issue)
                    last_error = issue
                    continue
                
                # Validate (agent-specific logic)
                is_valid, reason = self.validate_output(result)
                if not is_valid:
                    print(f"{self.agent_name}: ✗ Validation failed: {reason}")
                    quality_issues.append(reason)
                    last_error = reason
                    continue
                
                # All checks passed!
                result['agent'] = self.agent_name
                result['attempt'] = attempt + 1
                result['quality_score'] = self.calculate_quality_score(result)
                result['validation_passed'] = True
                print(f"{self.agent_name}: ✓ Success on attempt {attempt + 1} (Quality: {result['quality_score']:.2f})")
                return result
                
            except json.JSONDecodeError as e:
                print(f"{self.agent_name}: JSON parse error on attempt {attempt + 1}: {e}")
                last_error = f"JSON parse error: {str(e)}"
                quality_issues.append(last_error)
            except Exception as e:
                print(f"{self.agent_name}: Error on attempt {attempt + 1}: {e}")
                last_error = str(e)
                quality_issues.append(last_error)
        
        # All retries failed - REFUSE to proceed
        print(f"{self.agent_name}: ✗ QUALITY CHECK FAILED after {self.max_retries} attempts")
        return {
            "agent": self.agent_name,
            "error": last_error,
            "quality_issues": quality_issues,
            "success": False,
            "validation_passed": False,
            "requires_human_review": True,
            "confidence": 0.0
        }
    
    def _check_critical_fields(self, output: Dict[str, Any]) -> list:
        """
        Check if critical fields are missing or marked as "Not found"
        Returns list of missing field names
        """
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
        retry_instruction = ""
        if attempt > 0 and quality_issues:
            retry_instruction = f"\n\nIMPORTANT: Previous attempts failed due to:\n"
            for issue in quality_issues[-3:]:  # Last 3 issues
                retry_instruction += f"- {issue}\n"
            retry_instruction += "\nBe MORE THOROUGH. Extract ALL information carefully."
        
        full_prompt = f"{system_prompt}{retry_instruction}\n\nMessage:\n{message_text}\n\nJSON Response:"
        
        response = self.model.generate_content(full_prompt)
        result_text = response.text.strip()
        
        # Clean JSON from markdown
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        return json.loads(result_text)
    
    def calculate_quality_score(self, output: Dict[str, Any]) -> float:
        """
        Calculate quality score (0-1) based on:
        - Confidence level
        - Critical fields completeness
        - Validation passing
        Override in subclasses for more specific scoring
        """
        score = 0.0
        
        # Base confidence
        score += output.get('confidence', 0) * 0.5
        
        # Critical fields completeness
        critical_fields = self.get_critical_fields()
        if critical_fields:
            extracted = output.get('extracted_info', {})
            found_count = sum(1 for f in critical_fields if extracted.get(f) not in ['Not found', 'Not specified', '', None])
            completeness = found_count / len(critical_fields)
            score += completeness * 0.3
        
        # Validation passed
        if output.get('validation_passed', False):
            score += 0.2
        
        return min(score, 1.0)