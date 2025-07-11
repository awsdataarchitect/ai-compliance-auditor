"""
Simplified Lambda handler for Audit Logger function - MVP version.
"""
import json
import logging
import os
import boto3
from datetime import datetime
from typing import Dict, Any
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')


def convert_floats_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(v) for v in obj]
    else:
        return obj


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Simplified audit logger - logs events to DynamoDB for MVP testing.
    """
    try:
        logger.info(f"Processing audit logging: {json.dumps(event)}")
        
        # Extract audit event data
        audit_event = event.get('audit_event', {})
        
        # Get table name from environment
        table_name = os.environ.get('AUDIT_TABLE_NAME', 'ai-compliance-audit-logs')
        table = dynamodb.Table(table_name)
        
        # Create audit record
        audit_record = {
            'audit_id': f"audit-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{context.aws_request_id[:8]}",
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': audit_event.get('event_type', 'UNKNOWN'),
            'review_id': audit_event.get('review_id', 'unknown'),
            'user_id': audit_event.get('user_id', 'unknown'),
            'product_id': audit_event.get('product_id', 'unknown'),
            'region': audit_event.get('region', 'us-east-1'),
            'analysis_results': audit_event.get('analysis_results', {}),
            'policy_decision': audit_event.get('policy_decision', {}),
            'processing_duration_ms': audit_event.get('processing_duration_ms', 0),
            'ttl': int((datetime.utcnow().timestamp() + (365 * 24 * 60 * 60)))  # 1 year TTL
        }
        
        # Convert floats to Decimal for DynamoDB
        audit_record = convert_floats_to_decimal(audit_record)
        
        # Store in DynamoDB
        table.put_item(Item=audit_record)
        
        response = {
            'statusCode': 200,
            'audit_id': audit_record['audit_id'],
            'events_processed': 1,
            'events_failed': 0
        }
        
        logger.info(f"Audit event logged successfully: {audit_record['audit_id']}")
        return response
        
    except Exception as e:
        logger.error(f"Error in audit logging: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'events_processed': 0,
            'events_failed': 1
        }
