"""
Lambda handler for Review Auditor function with real Bedrock Nova Premier integration.
Version: 2.0 - Real Bedrock Integration
"""
import json
import logging
import os
import time
import boto3
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock client
bedrock_runtime = boto3.client('bedrock-runtime')

# Model configuration - Using Nova Premier inference profile
MODEL_ID = "us.amazon.nova-premier-v1:0"
INFERENCE_CONFIG = {
    "temperature": 0.1,
    "max_tokens": 1000
}


def create_analysis_prompt(content: str, product_category: str, rating: int) -> str:
    """Create a structured prompt for Nova Premier analysis."""
    return f"""You are an AI content moderation expert. Analyze the following product review for toxicity, bias, and hallucination. Provide scores from 0-10 where:

TOXICITY (0=completely safe, 10=extremely toxic):
- Hate speech, harassment, threats
- Profanity, offensive language
- Personal attacks

BIAS (0=no bias, 10=extremely biased):
- Unfair generalizations
- Discriminatory language
- Prejudiced statements

HALLUCINATION (0=factual, 10=completely false):
- False claims about product features
- Impossible or unrealistic statements
- Contradictory information

REVIEW TO ANALYZE:
Product Category: {product_category}
Rating: {rating}/5
Content: "{content}"

Respond ONLY with valid JSON in this exact format:
{{
  "toxicity_score": <number 0-10>,
  "bias_score": <number 0-10>, 
  "hallucination_score": <number 0-10>,
  "explanations": {{
    "toxicity": "<brief explanation>",
    "bias": "<brief explanation>",
    "hallucination": "<brief explanation>"
  }}
}}"""


def call_bedrock_nova_premier(prompt: str) -> Dict[str, Any]:
    """Call Bedrock Nova Premier model for analysis."""
    try:
        # Prepare the request body for Nova Premier
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "temperature": INFERENCE_CONFIG["temperature"],
                "maxTokens": INFERENCE_CONFIG["max_tokens"]
            }
        }
        
        # Call Bedrock Converse API
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=request_body["messages"],
            inferenceConfig=request_body["inferenceConfig"]
        )
        
        # Extract the response text
        response_text = response['output']['message']['content'][0]['text']
        logger.info(f"Bedrock response: {response_text}")
        
        # Parse JSON response
        try:
            # Clean up the response text - Nova Premier sometimes wraps JSON in markdown code blocks
            clean_response = response_text.strip()
            if clean_response.startswith('```json'):
                # Remove markdown code block markers
                clean_response = clean_response.replace('```json\n', '').replace('\n```', '').strip()
            elif clean_response.startswith('```'):
                # Remove generic code block markers
                clean_response = clean_response.replace('```\n', '').replace('\n```', '').strip()
            
            analysis_result = json.loads(clean_response)
            return analysis_result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock JSON response: {e}")
            logger.error(f"Raw response: {response_text}")
            # Return fallback analysis
            return {
                "toxicity_score": 5.0,
                "bias_score": 5.0,
                "hallucination_score": 5.0,
                "explanations": {
                    "toxicity": "Analysis parsing failed - using moderate risk score",
                    "bias": "Analysis parsing failed - using moderate risk score", 
                    "hallucination": "Analysis parsing failed - using moderate risk score"
                }
            }
            
    except Exception as e:
        logger.error(f"Bedrock API call failed: {str(e)}")
        # Return high-risk fallback scores
        return {
            "toxicity_score": 8.0,
            "bias_score": 8.0,
            "hallucination_score": 8.0,
            "explanations": {
                "toxicity": f"Bedrock API failed: {str(e)} - defaulting to high risk",
                "bias": f"Bedrock API failed: {str(e)} - defaulting to high risk",
                "hallucination": f"Bedrock API failed: {str(e)} - defaulting to high risk"
            }
        }


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for review auditing with real Bedrock integration.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Processing review audit request: {json.dumps(event)}")
        
        # Extract review content
        content = event.get('content', '')
        review_id = event.get('review_id', 'unknown')
        product_category = event.get('product_category', 'other')
        rating = int(event.get('rating', 3))
        
        if not content or len(content.strip()) < 5:
            return {
                'statusCode': 400,
                'error': 'Review content is required and must be at least 5 characters',
                'analysis': {
                    'toxicity_score': 10.0,
                    'bias_score': 10.0,
                    'hallucination_score': 10.0,
                    'explanations': {
                        'toxicity': 'Invalid content - validation failed',
                        'bias': 'Invalid content - validation failed',
                        'hallucination': 'Invalid content - validation failed'
                    }
                }
            }
        
        # Create analysis prompt
        prompt = create_analysis_prompt(content, product_category, rating)
        logger.info(f"Analyzing review {review_id} with Bedrock Nova Premier")
        
        # Call Bedrock Nova Premier
        analysis_result = call_bedrock_nova_premier(prompt)
        
        # Validate scores are within expected range
        for score_key in ['toxicity_score', 'bias_score', 'hallucination_score']:
            score = analysis_result.get(score_key, 5.0)
            if not isinstance(score, (int, float)) or score < 0 or score > 10:
                logger.warning(f"Invalid {score_key}: {score}, defaulting to 5.0")
                analysis_result[score_key] = 5.0
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        response = {
            'statusCode': 200,
            'review_id': review_id,
            'analysis': analysis_result,
            'model_metadata': {
                'model_id': MODEL_ID,
                'prompt_version': '2.0',
                'inference_config': INFERENCE_CONFIG
            },
            'processing_time_ms': processing_time
        }
        
        logger.info(f"Bedrock analysis completed for review {review_id} in {processing_time:.2f}ms")
        logger.info(f"Scores - Toxicity: {analysis_result['toxicity_score']}, Bias: {analysis_result['bias_score']}, Hallucination: {analysis_result['hallucination_score']}")
        
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error in review auditor: {str(e)}")
        
        return {
            'statusCode': 500,
            'error': str(e),
            'analysis': {
                'toxicity_score': 10.0,
                'bias_score': 10.0,
                'hallucination_score': 10.0,
                'explanations': {
                    'toxicity': f'System error: {str(e)}',
                    'bias': f'System error: {str(e)}',
                    'hallucination': f'System error: {str(e)}'
                }
            }
        }
