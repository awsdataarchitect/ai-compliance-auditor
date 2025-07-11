"""
Bedrock client wrapper for AI Compliance Auditor.
Handles interactions with Amazon Bedrock Nova Premier model.
"""
import boto3
import json
import time
import logging
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError, BotoCoreError
from dataclasses import dataclass
import asyncio
from functools import wraps
import random

from config import config, AWS_REGION
from models import ModelMetadata

logger = logging.getLogger(__name__)


@dataclass
class BedrockResponse:
    """Response from Bedrock model invocation."""
    content: str
    model_metadata: ModelMetadata
    raw_response: Dict[str, Any]
    processing_time_ms: int
    cost_usd: Optional[float] = None


class BedrockError(Exception):
    """Custom exception for Bedrock-related errors."""
    pass


class BedrockThrottleError(BedrockError):
    """Exception for throttling errors."""
    pass


class BedrockValidationError(BedrockError):
    """Exception for validation errors."""
    pass


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for exponential backoff retry logic."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except BedrockThrottleError as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Throttled, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(delay)
                except Exception as e:
                    # Don't retry for non-throttling errors
                    raise e
            
            raise last_exception
        return wrapper
    return decorator


class BedrockClient:
    """Client for interacting with Amazon Bedrock Nova Premier model."""
    
    def __init__(self):
        self.client = boto3.client('bedrock-runtime', region_name=AWS_REGION)
        self.model_id = config.get_parameter('bedrock_model_id', 'amazon.nova-premier-v1:0')
        self.prompt_version = config.get_parameter('prompt_version', '1.0')
        self.max_retries = int(config.get_parameter('max_retries', '3'))
        self.timeout_seconds = int(config.get_parameter('timeout_seconds', '30'))
        
        # Default inference configuration
        self.default_inference_config = {
            'maxTokens': 1000,
            'temperature': 0.1,
            'topP': 0.9,
            'stopSequences': []
        }
        
        logger.info(f"Initialized Bedrock client with model: {self.model_id}")
    
    def _build_prompt_template(self, template_type: str) -> str:
        """Build prompt template for different analysis types."""
        templates = {
            'toxicity_analysis': """
You are an expert content moderator analyzing product reviews for toxicity. 

Analyze the following product review and provide a toxicity score from 0-10 where:
- 0-2: Clean, respectful content
- 3-4: Mildly negative but acceptable
- 5-6: Moderately toxic, contains harsh criticism or mild profanity
- 7-8: Highly toxic, contains offensive language or personal attacks
- 9-10: Extremely toxic, contains hate speech or severe abuse

Review to analyze: "{content}"

Respond in JSON format:
{{
    "toxicity_score": <float between 0-10>,
    "explanation": "<detailed explanation of the score>",
    "confidence": <float between 0-1>,
    "detected_issues": ["<list of specific issues found>"]
}}
""",
            
            'bias_analysis': """
You are an expert content moderator analyzing product reviews for bias and discrimination.

Analyze the following product review for bias indicators including:
- Racial or ethnic bias
- Gender bias
- Religious bias
- Age discrimination
- Nationality-based prejudice
- Other forms of discrimination

Provide a bias score from 0-10 where:
- 0-2: No bias detected
- 3-4: Subtle bias or stereotyping
- 5-6: Moderate bias with clear discriminatory language
- 7-8: Strong bias with offensive stereotypes
- 9-10: Extreme bias with hate speech

Review to analyze: "{content}"

Respond in JSON format:
{{
    "bias_score": <float between 0-10>,
    "explanation": "<detailed explanation of the score>",
    "confidence": <float between 0-1>,
    "bias_types": ["<list of bias types detected>"],
    "problematic_phrases": ["<specific phrases that indicate bias>"]
}}
""",
            
            'hallucination_analysis': """
You are an expert content moderator analyzing product reviews for hallucinated or fabricated claims.

Analyze the following product review for claims that appear to be:
- Invented features not typically found in products
- Exaggerated capabilities
- Technical specifications that seem unrealistic
- Claims that contradict common product knowledge

Provide a hallucination score from 0-10 where:
- 0-2: All claims appear realistic and verifiable
- 3-4: Minor exaggerations but generally believable
- 5-6: Some questionable claims that may be exaggerated
- 7-8: Multiple unrealistic claims or significant exaggerations
- 9-10: Clearly fabricated features or impossible claims

Review to analyze: "{content}"

Respond in JSON format:
{{
    "hallucination_score": <float between 0-10>,
    "explanation": "<detailed explanation of the score>",
    "confidence": <float between 0-1>,
    "questionable_claims": ["<list of specific claims that seem fabricated>"],
    "realistic_claims": ["<list of claims that seem genuine>"]
}}
""",
            
            'summarization': """
You are an expert content summarizer creating factual product review summaries.

Create a concise 3-sentence summary of the following product reviews. Follow these guidelines:
- Only include information explicitly mentioned in the reviews
- Do not invent or hallucinate product features
- Exclude any abusive, toxic, or policy-violating content
- Focus on factual observations about the product
- Maintain a neutral, informative tone

Reviews to summarize:
{reviews_content}

Policy constraints applied:
- Maximum toxicity score allowed: {max_toxicity}
- Maximum bias score allowed: {max_bias}
- Maximum hallucination score allowed: {max_hallucination}

Respond in JSON format:
{{
    "summary": "<3-sentence factual summary>",
    "confidence": <float between 0-1>,
    "sources_used": <number of reviews used>,
    "excluded_content": ["<reasons for excluding any content>"]
}}
"""
        }
        
        return templates.get(template_type, "")
    
    @retry_with_exponential_backoff(max_retries=3)
    async def _invoke_model(self, prompt: str, inference_config: Optional[Dict[str, Any]] = None) -> BedrockResponse:
        """Invoke the Bedrock model with retry logic."""
        start_time = time.time()
        
        # Use provided config or default
        config_to_use = inference_config or self.default_inference_config
        
        # Build the request body for Nova Premier
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": config_to_use
        }
        
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract content from Nova Premier response format
            content = ""
            if 'output' in response_body and 'message' in response_body['output']:
                message = response_body['output']['message']
                if 'content' in message and len(message['content']) > 0:
                    content = message['content'][0].get('text', '')
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Calculate estimated cost (approximate pricing for Nova Premier)
            input_tokens = response_body.get('usage', {}).get('inputTokens', 0)
            output_tokens = response_body.get('usage', {}).get('outputTokens', 0)
            
            # Approximate pricing (adjust based on actual Nova Premier pricing)
            input_cost_per_1k = 0.0008  # $0.0008 per 1K input tokens
            output_cost_per_1k = 0.0032  # $0.0032 per 1K output tokens
            
            estimated_cost = (input_tokens / 1000 * input_cost_per_1k) + (output_tokens / 1000 * output_cost_per_1k)
            
            # Create model metadata
            model_metadata = ModelMetadata(
                model_id=self.model_id,
                prompt_version=self.prompt_version,
                inference_config=config_to_use,
                processing_time_ms=processing_time_ms,
                cost_usd=estimated_cost
            )
            
            return BedrockResponse(
                content=content,
                model_metadata=model_metadata,
                raw_response=response_body,
                processing_time_ms=processing_time_ms,
                cost_usd=estimated_cost
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code in ['ThrottlingException', 'ServiceQuotaExceededException']:
                raise BedrockThrottleError(f"Bedrock throttling: {error_message}")
            elif error_code in ['ValidationException', 'InvalidRequestException']:
                raise BedrockValidationError(f"Bedrock validation error: {error_message}")
            else:
                raise BedrockError(f"Bedrock error ({error_code}): {error_message}")
        
        except BotoCoreError as e:
            raise BedrockError(f"Bedrock connection error: {str(e)}")
        
        except Exception as e:
            raise BedrockError(f"Unexpected Bedrock error: {str(e)}")
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response from model, handling potential formatting issues."""
        try:
            # Try direct JSON parsing first
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON-like content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            # If all else fails, return a default structure
            logger.warning(f"Failed to parse JSON response: {content}")
            return {
                "error": "Failed to parse model response",
                "raw_content": content
            }
    
    async def analyze_toxicity(self, content: str, inference_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze content for toxicity."""
        prompt_template = self._build_prompt_template('toxicity_analysis')
        prompt = prompt_template.format(content=content)
        
        response = await self._invoke_model(prompt, inference_config)
        parsed_response = self._parse_json_response(response.content)
        
        # Add metadata to response
        parsed_response['model_metadata'] = response.model_metadata.dict()
        
        return parsed_response
    
    async def analyze_bias(self, content: str, inference_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze content for bias."""
        prompt_template = self._build_prompt_template('bias_analysis')
        prompt = prompt_template.format(content=content)
        
        response = await self._invoke_model(prompt, inference_config)
        parsed_response = self._parse_json_response(response.content)
        
        # Add metadata to response
        parsed_response['model_metadata'] = response.model_metadata.dict()
        
        return parsed_response
    
    async def analyze_hallucination(self, content: str, inference_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze content for hallucinated claims."""
        prompt_template = self._build_prompt_template('hallucination_analysis')
        prompt = prompt_template.format(content=content)
        
        response = await self._invoke_model(prompt, inference_config)
        parsed_response = self._parse_json_response(response.content)
        
        # Add metadata to response
        parsed_response['model_metadata'] = response.model_metadata.dict()
        
        return parsed_response
    
    async def generate_summary(self, reviews_content: str, max_toxicity: float = 5.0, 
                             max_bias: float = 3.0, max_hallucination: float = 6.0,
                             inference_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a summary of multiple reviews."""
        prompt_template = self._build_prompt_template('summarization')
        prompt = prompt_template.format(
            reviews_content=reviews_content,
            max_toxicity=max_toxicity,
            max_bias=max_bias,
            max_hallucination=max_hallucination
        )
        
        # Use slightly different config for summarization (more tokens)
        summary_config = (inference_config or self.default_inference_config).copy()
        summary_config['maxTokens'] = 1500  # Allow more tokens for summaries
        
        response = await self._invoke_model(prompt, summary_config)
        parsed_response = self._parse_json_response(response.content)
        
        # Add metadata to response
        parsed_response['model_metadata'] = response.model_metadata.dict()
        
        return parsed_response
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the Bedrock service."""
        try:
            # Simple test invocation
            test_prompt = "Respond with 'OK' if you can process this request."
            response = await self._invoke_model(test_prompt, {'maxTokens': 10})
            
            return {
                'status': 'healthy',
                'model_id': self.model_id,
                'response_time_ms': response.processing_time_ms,
                'test_response': response.content[:50]  # First 50 chars
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'model_id': self.model_id,
                'error': str(e)
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the configured model."""
        return {
            'model_id': self.model_id,
            'prompt_version': self.prompt_version,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'default_inference_config': self.default_inference_config
        }


# Global Bedrock client instance
bedrock_client = BedrockClient()