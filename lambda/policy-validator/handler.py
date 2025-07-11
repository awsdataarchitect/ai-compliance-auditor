"""
Simplified Lambda handler for Policy Validator function - MVP version.
"""
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Simplified policy validator - uses basic thresholds for MVP testing.
    """
    try:
        logger.info(f"Processing policy validation: {json.dumps(event)}")
        
        # Extract analysis results
        analysis_result = event.get('analysis_result', {})
        policy_context = event.get('policy_context', {})
        
        toxicity_score = analysis_result.get('toxicity_score', 10.0)
        bias_score = analysis_result.get('bias_score', 10.0)
        hallucination_score = analysis_result.get('hallucination_score', 10.0)
        
        # Simple policy thresholds
        compliance_mode = policy_context.get('compliance_mode', 'standard')
        
        if compliance_mode == 'strict':
            toxicity_threshold = 3.0
            bias_threshold = 2.0
            hallucination_threshold = 4.0
        elif compliance_mode == 'mild':
            toxicity_threshold = 8.0
            bias_threshold = 7.0
            hallucination_threshold = 8.0
        else:  # standard
            toxicity_threshold = 5.0
            bias_threshold = 4.0
            hallucination_threshold = 6.0
        
        # Check if content passes policy
        violations = []
        if toxicity_score >= toxicity_threshold:
            violations.append('TOXICITY_THRESHOLD_EXCEEDED')
        if bias_score >= bias_threshold:
            violations.append('BIAS_THRESHOLD_EXCEEDED')
        if hallucination_score >= hallucination_threshold:
            violations.append('HALLUCINATION_THRESHOLD_EXCEEDED')
        
        decision = 'DENY' if violations else 'ALLOW'
        
        validation_result = {
            'decision': decision,
            'reasons': violations if violations else ['CONTENT_APPROVED'],
            'explanation': f'Content {"rejected" if violations else "approved"} based on {compliance_mode} compliance mode',
            'thresholds_applied': {
                'toxicity': toxicity_threshold,
                'bias': bias_threshold,
                'hallucination': hallucination_threshold
            }
        }
        
        response = {
            'statusCode': 200,
            'validation_result': validation_result
        }
        
        logger.info(f"Policy validation completed: {decision}")
        return response
        
    except Exception as e:
        logger.error(f"Error in policy validation: {str(e)}")
        return {
            'statusCode': 500,
            'validation_result': {
                'decision': 'DENY',
                'reasons': ['SYSTEM_ERROR'],
                'explanation': f'Policy validation failed: {str(e)}'
            }
        }
