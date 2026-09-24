"""
LLM Client - Compatibility wrapper using unified LLM Manager
"""
import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
from collections.abc import Generator

# Fix import issues
try:
    from ..core.shared_config import MODEL_NAME
except ImportError:
    # If relative import fails, attempt absolute import
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from core.shared_config import MODEL_NAME

# Import unified LLM Manager
try:
    from ..core.llm_manager import get_llm_manager
except ImportError:
    # If relative import fails, attempt absolute import
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from core.llm_manager import get_llm_manager

logger = logging.getLogger(__name__)

class LLMClient:
    """LLM Client - Compatibility wrapper"""
    
    def __init__(self):
        self.model = MODEL_NAME
        self.llm_manager = get_llm_manager()

    def get_max_srt_chars(self) -> int:
        """
        Returns model-aware maximum character budget for subtitle (SRT) text
        to ensure prompt + response remains safely under the provider's context limit.
        """
        model = ""
        try:
            if hasattr(self.llm_manager, "current_provider") and self.llm_manager.current_provider:
                model = str(self.llm_manager.current_provider.model_name).lower()
            elif hasattr(self, "model") and self.model:
                model = str(self.model).lower()
        except Exception:
            model = ""

        # qwen-flash-character hard limit is 32,768 chars total -> budget 18,000 for SRT
        if "character" in model or "flash" in model:
            return 18000
        elif "turbo" in model or "plus" in model:
            return 26000
        elif "gemini" in model:
            return 60000
        elif "gpt-4" in model:
            return 45000
        return 18000
    
    def call(self, prompt: str, input_data: Any = None, task: str = "general", model: Optional[str] = None, **kwargs) -> str:
        """
        Call LLM API using unified LLM Manager and ModelRouter
        """
        try:
            if not model:
                active_provider = self.llm_manager.settings.get("llm_provider", "dashscope")
                if active_provider != "dashscope":
                    model = self.llm_manager.settings.get("model_name")
                else:
                    from ..core.model_router import model_router
                    model = model_router.next(task)
            return self.llm_manager.call(prompt, input_data, model=model, **kwargs)
        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            raise
    
    def call_with_retry(self, prompt: str, input_data: Any = None, max_retries: int = 3, task: str = "general", model: Optional[str] = None, **kwargs) -> str:
        """
        API call with ModelRouter failover across candidate models in pool
        """
        active_provider = self.llm_manager.settings.get("llm_provider", "dashscope")
        if active_provider != "dashscope" or model:
            effective_model = model or self.llm_manager.settings.get("model_name")
            try:
                return self.llm_manager.call_with_retry(prompt, input_data, max_retries=max_retries, model=effective_model, **kwargs)
            except Exception as e:
                logger.error(f"LLM retry call failed with provider {active_provider} / model {effective_model}: {str(e)}")
                raise

        from ..core.model_router import model_router
        def _invoke_with_model(m_name: str) -> str:
            return self.llm_manager.call(prompt, input_data, model=m_name, **kwargs)

        try:
            return model_router.call_with_fallback(task=task, call_fn=_invoke_with_model, max_retries=max_retries)
        except Exception as e:
            logger.error(f"LLM failover router call failed on task {task}: {str(e)}")
            raise
    
    def _preprocess_llm_response(self, response: str) -> str:
        """
        Preprocess LLM response, stripping non-JSON preambles and footers
        """
        # Remove introductory headers and explanations
        lines = response.split('\n')
        json_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('[') or stripped.startswith('{'):
                json_start = i
                break
        
        if json_start >= 0:
            response = '\n'.join(lines[json_start:])
        
        # Remove trailing non-JSON content
        if '```' in response:
            # If multiple code blocks exist, take relevant content
            parts = response.split('```')
            if len(parts) > 1:
                response = parts[0]
        
        return response.strip()
    
    def _auto_fix_response(self, response: str) -> str:
        """
        Automatically repair common JSON syntax issues
        """
        # Remove BOM and special control characters
        response = response.lstrip('\ufeff')
        response = response.strip()
        
        # Fix fullwidth quotes
        response = response.replace('"', '\"').replace('"', '\"')
        
        return response
    
    def _validate_json_structure(self, parsed_data: Any) -> bool:
        """
        Validate integrity of JSON structure
        """
        try:
            if not isinstance(parsed_data, list):
                logger.error(f"Response is not an array format, actual type: {type(parsed_data)}")
                return False
            
            for i, item in enumerate(parsed_data):
                if not isinstance(item, dict):
                    logger.error(f"Element {i} is not an object format, actual type: {type(item)}")
                    return False
                    
                # Check required fields
                if 'outline' in item or 'start_time' in item or 'end_time' in item:
                    required_fields = ['outline', 'start_time', 'end_time']
                    for field in required_fields:
                        if field not in item:
                            logger.error(f"Element {i} missing required field: {field}")
                            return False
        except Exception as e:
            logger.error(f"Error validating JSON structure: {e}")
            return False
        
        return True
    
    def parse_json_response(self, response: str) -> Any:
        """
        Parse JSON object from text that may contain Markdown code fences.
        This function features multi-tier fault tolerance:
        1. Preprocess response to strip non-JSON preambles.
        2. Extract from Markdown code blocks first.
        3. If failed, attempt direct parsing of sanitized response.
        4. If still failed, locate JSON structures using regex.
        5. Attempt automatic syntax repair on corrupted JSON.
        """
        
        def sanitize_string(s: str) -> str:
            """Enhanced sanitization function to strip malformed characters"""
            # Remove BOM markers
            s = s.lstrip('\ufeff')
            # Strip whitespace
            s = s.strip()
            # Strip control characters (preserve tabs and newlines)
            s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
            return s
        
        def fix_common_json_errors(json_str: str) -> str:
            """Repair common JSON syntax flaws"""
            # Record raw string for debugging
            original_str = json_str
            
            # 1. Repair missing commas
            json_str = re.sub(r'}\s*{', '},{', json_str)
            json_str = re.sub(r']\s*\[', '],[', json_str)
            
            # 2. Repair missing commas between objects
            json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
            
            # 3. Repair trailing commas
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # 4. Replace single quotes with double quotes
            json_str = re.sub(r"'([^']*?)'\s*:", r'"\1":', json_str)
            json_str = re.sub(r":\s*'([^']*?)'", r': "\1"', json_str)
            
            # 5. Quote unquoted field names
            json_str = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_str)
            
            # 6. Repair unescaped newlines
            json_str = re.sub(r'\n\s*\n', '\n', json_str)
            
            # 7. Ensure brackets and braces close properly
            # Count open and close brackets
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            open_brackets = json_str.count('[')
            close_brackets = json_str.count(']')
            
            # Close unmatched brackets
            if open_braces > close_braces:
                json_str += '}' * (open_braces - close_braces)
            if open_brackets > close_brackets:
                json_str += ']' * (open_brackets - close_brackets)
            
            # Log repair progress
            if json_str != original_str:
                logger.debug(f"JSON before repair: {original_str[:100]}...")
                logger.debug(f"JSON after repair: {json_str[:100]}...")
            
            return json_str

        response = response.strip()
        
        # 0. Preprocess response, strip non-JSON preambles
        response = self._preprocess_llm_response(response)
        logger.debug(f"Preprocessed response: {response[:200]}...")
        
        # 1. Extract from Markdown code fence if present
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.DOTALL)
        if match:
            json_str = sanitize_string(match.group(1))
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # Record error position and context
                error_pos = e.pos if hasattr(e, 'pos') else 0
                context_start = max(0, error_pos - 50)
                context_end = min(len(json_str), error_pos + 50)
                context = json_str[context_start:context_end]
                logger.error(f"JSON parsing failed at position {error_pos}, context: ...{context}...")
                logger.warning(f"Failed to parse content extracted from Markdown: {e}. Attempting syntax repair before re-parsing.")
                
                # Attempt syntax repair before re-parsing
                try:
                    fixed_json = fix_common_json_errors(json_str)
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    logger.warning("Still failed after repair; attempting full response parsing.")
        
        # 2. If no Markdown or Markdown parsing failed, attempt full response
        try:
            sanitized_response = sanitize_string(response)
            return json.loads(sanitized_response)
        except json.JSONDecodeError:
            # 3. If direct parsing fails, use regex to locate JSON
            logger.warning("Direct parse failed, searching for JSON via regex...")
            json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', response, re.DOTALL)
            if json_match:
                json_str = sanitize_string(json_match.group())
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    # Try json_repair library first for unescaped quotes/syntax repairs
                    try:
                        import json_repair
                        repaired_data = json_repair.loads(json_str)
                        if repaired_data:
                            logger.info("Successfully repaired malformed LLM JSON using json_repair.")
                            return repaired_data
                    except Exception:
                        pass

                    # 4. Final attempt to repair syntax flaws
                    try:
                        fixed_json = fix_common_json_errors(json_str)
                        return json.loads(fixed_json)
                    except json.JSONDecodeError as final_e:
                        # Try json_repair on full response as last ditch
                        try:
                            import json_repair
                            repaired_data = json_repair.loads(response)
                            if repaired_data:
                                logger.info("Successfully repaired malformed LLM JSON from full response using json_repair.")
                                return repaired_data
                        except Exception:
                            pass

                        logger.error(f"Final parse attempt failed: {final_e}")
                        # Save raw response for debugging
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                            f.write(response)
                            logger.error(f"Raw response saved to {f.name} for debugging")
                        raise ValueError(f"Failed to parse valid JSON from response: {response[:200]}...") from final_e
            
            # If regex fails as well, fail completely
            try:
                import json_repair
                repaired_data = json_repair.loads(response)
                if repaired_data:
                    return repaired_data
            except Exception:
                pass
            raise ValueError(f"Failed to parse valid JSON from response: {response[:200]}...")
    
    def get_current_provider_info(self) -> Dict[str, Any]:
        """Get current provider information"""
        return self.llm_manager.get_current_provider_info()