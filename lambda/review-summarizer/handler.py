"""
Lambda handler for Review Summarizer function with real Bedrock Nova Premier integration.
"""
import json
import logging
import boto3
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock client
bedrock_runtime = boto3.client('bedrock-runtime')

# Model configuration - Using Nova Premier inference profile
MODEL_ID = "us.amazon.nova-premier-v1:0"
INFERENCE_CONFIG = {
    "temperature": 0.3,
    "max_tokens": 500
}


def create_summarization_prompt(reviews: List[Dict], product_id: str) -> str:
    """Create a structured prompt for Nova Premier summarization."""
    
    # Prepare review data for the prompt
    review_texts = []
    total_rating = 0
    approved_count = 0
    
    for review in reviews:
        if review.get('analysis_passed', True):  # Only include approved reviews
            content = review.get('content', '')
            rating = review.get('rating', 3)
            if isinstance(rating, str):
                rating = float(rating)
            
            review_texts.append(f"Rating: {rating}/5 - {content}")
            total_rating += rating
            approved_count += 1
    
    if approved_count == 0:
        return None
    
    avg_rating = total_rating / approved_count
    reviews_text = "\n".join(review_texts[:10])  # Limit to first 10 reviews
    
    return f"""You are an expert at analyzing customer reviews and creating concise, helpful summaries. 

Analyze these {approved_count} customer reviews for product {product_id} and create a balanced summary.

REVIEWS TO ANALYZE:
{reviews_text}

AVERAGE RATING: {avg_rating:.1f}/5

Create a summary that:
1. Reflects the overall sentiment accurately
2. Mentions key themes (quality, value, functionality, etc.)
3. Is 1-2 sentences maximum
4. Is helpful for potential customers
5. Balances positive and negative feedback appropriately

Respond ONLY with valid JSON in this exact format:
{{
  "summary": "<1-2 sentence summary>",
  "sentiment": "<positive|mixed|negative>",
  "key_themes": ["<theme1>", "<theme2>", "<theme3>"],
  "confidence": <0.0-1.0>
}}"""


def call_bedrock_for_summary(prompt: str) -> Dict[str, Any]:
    """Call Bedrock Nova Premier for review summarization."""
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
        logger.info(f"Bedrock summarization response: {response_text}")
        
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
            
            summary_result = json.loads(clean_response)
            return summary_result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock JSON response: {e}")
            logger.error(f"Raw response: {response_text}")
            # Return fallback summary
            return {
                "summary": "Customer reviews provide mixed feedback about this product.",
                "sentiment": "mixed",
                "key_themes": ["quality", "value", "functionality"],
                "confidence": 0.5
            }
            
    except Exception as e:
        logger.error(f"Bedrock summarization API call failed: {str(e)}")
        # Return fallback summary
        return {
            "summary": f"Unable to generate summary due to system error: {str(e)}",
            "sentiment": "mixed",
            "key_themes": ["system_error"],
            "confidence": 0.0
        }


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for review summarization with real Bedrock integration.
    """
    try:
        logger.info(f"Processing review summarization: {json.dumps(event)}")
        
        # Extract reviews data
        reviews = event.get('reviews', [])
        product_id = event.get('product_id', 'unknown')
        
        if not reviews:
            return {
                'statusCode': 400,
                'error': 'No reviews provided for summarization'
            }
        
        # Filter and process reviews
        total_reviews = len(reviews)
        included_reviews = [r for r in reviews if r.get('analysis_passed', True)]
        excluded_reviews = total_reviews - len(included_reviews)
        
        if not included_reviews:
            return {
                'statusCode': 200,
                'product_id': product_id,
                'summary': 'No approved reviews available for summarization.',
                'summary_metadata': {
                    'reviews_processed': total_reviews,
                    'reviews_included': 0,
                    'reviews_excluded': excluded_reviews,
                    'average_rating': 0,
                    'sentiment': 'neutral',
                    'confidence': 0.0,
                    'key_themes': [],
                    'exclusion_reasons': ['ALL_REVIEWS_REJECTED']
                }
            }
        
        # Calculate basic statistics
        ratings = []
        for r in included_reviews:
            rating = r.get('rating', 3)
            if isinstance(rating, str):
                rating = float(rating)
            ratings.append(rating)
        
        avg_rating = sum(ratings) / len(ratings)
        
        # Create prompt for Bedrock
        prompt = create_summarization_prompt(included_reviews, product_id)
        
        if prompt is None:
            return {
                'statusCode': 200,
                'product_id': product_id,
                'summary': 'No valid reviews available for summarization.',
                'summary_metadata': {
                    'reviews_processed': total_reviews,
                    'reviews_included': 0,
                    'reviews_excluded': excluded_reviews,
                    'average_rating': 0,
                    'sentiment': 'neutral',
                    'confidence': 0.0,
                    'key_themes': []
                }
            }
        
        # Call Bedrock for AI-powered summarization
        logger.info(f"Generating AI summary for {len(included_reviews)} reviews using Bedrock Nova Premier")
        bedrock_result = call_bedrock_for_summary(prompt)
        
        # Prepare response with Bedrock-generated summary
        summary_metadata = {
            'reviews_processed': total_reviews,
            'reviews_included': len(included_reviews),
            'reviews_excluded': excluded_reviews,
            'average_rating': float(avg_rating),
            'sentiment': bedrock_result.get('sentiment', 'mixed'),
            'confidence': bedrock_result.get('confidence', 0.5),
            'key_themes': bedrock_result.get('key_themes', []),
            'ai_generated': True,
            'model_used': MODEL_ID
        }
        
        response = {
            'statusCode': 200,
            'product_id': product_id,
            'summary': bedrock_result.get('summary', 'Summary generation completed.'),
            'summary_metadata': summary_metadata
        }
        
        logger.info(f"AI summary generated for product {product_id}: {len(included_reviews)} reviews processed")
        logger.info(f"Summary: {bedrock_result.get('summary', '')}")
        logger.info(f"Sentiment: {bedrock_result.get('sentiment', 'mixed')}, Confidence: {bedrock_result.get('confidence', 0.5)}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in review summarization: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'summary': 'Summary generation failed due to system error',
            'summary_metadata': {
                'reviews_processed': 0,
                'reviews_included': 0,
                'reviews_excluded': 0,
                'exclusion_reasons': ['SYSTEM_ERROR'],
                'ai_generated': False
            }
        }
