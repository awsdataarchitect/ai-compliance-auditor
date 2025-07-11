"""
Report Generator Lambda Function - MVP Version
Generates simple JSON compliance reports and stores them in S3
"""

import json
import logging
import os
import sys
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import asyncio
import boto3
from botocore.exceptions import ClientError

# Add the common layer to the path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from database import db_client, DatabaseClient
from models import EventType
from config import AWS_REGION

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
database = DatabaseClient()

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for report generation
    
    Args:
        event: Lambda event containing report parameters
        context: Lambda context
        
    Returns:
        Report generation result
    """
    try:
        logger.info(f"Processing report generation request: {json.dumps(event, default=str)}")
        
        # Extract event data
        report_type = event.get('report_type', 'compliance_summary')
        start_date_str = event.get('start_date')
        end_date_str = event.get('end_date')
        product_id = event.get('product_id')
        user_id = event.get('user_id')
        
        # Validate required parameters
        if not start_date_str or not end_date_str:
            raise ValueError("start_date and end_date are required")
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Generate report
        result = asyncio.run(generate_report(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            user_id=user_id,
            context=context
        ))
        
        # Prepare response
        response = {
            'statusCode': 200,
            'report_id': result['report_id'],
            'report_type': report_type,
            'report_url': result['report_url'],
            'report_size_bytes': result['report_size_bytes'],
            'processing_metadata': {
                'request_id': context.aws_request_id,
                'function_name': context.function_name,
                'generation_time_ms': result['generation_time_ms'],
                'records_processed': result['records_processed']
            }
        }
        
        logger.info(f"Report generation completed: {result['report_id']}")
        return response
        
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}", exc_info=True)
        
        # Return error response
        return {
            'statusCode': 500,
            'error': {
                'type': 'ReportGenerationError',
                'message': str(e),
                'request_id': context.aws_request_id if context else 'unknown'
            },
            'report_id': None,
            'report_url': None
        }

async def generate_report(
    report_type: str,
    start_date: datetime,
    end_date: datetime,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    context=None
) -> Dict[str, Any]:
    """
    Generate a compliance report
    
    Args:
        report_type: Type of report to generate
        start_date: Report start date
        end_date: Report end date
        product_id: Optional product filter
        user_id: Optional user filter
        context: Lambda context
        
    Returns:
        Report generation result
    """
    start_time = datetime.now(timezone.utc)
    report_id = str(uuid.uuid4())
    
    logger.info(f"Generating {report_type} report for period {start_date} to {end_date}")
    
    # Generate report based on type
    if report_type == 'compliance_summary':
        report_data = await generate_compliance_summary_report(start_date, end_date, product_id, user_id)
    elif report_type == 'policy_violations':
        report_data = await generate_policy_violations_report(start_date, end_date, product_id, user_id)
    elif report_type == 'processing_stats':
        report_data = await generate_processing_stats_report(start_date, end_date, product_id, user_id)
    else:
        raise ValueError(f"Unknown report type: {report_type}")
    
    # Add report metadata
    report_data['report_metadata'] = {
        'report_id': report_id,
        'report_type': report_type,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'filters': {
            'product_id': product_id,
            'user_id': user_id
        },
        'generator': {
            'function_name': context.function_name if context else 'unknown',
            'request_id': context.aws_request_id if context else 'unknown'
        }
    }
    
    # Convert to JSON and upload to S3
    report_json = json.dumps(report_data, indent=2, default=str)
    report_size_bytes = len(report_json.encode('utf-8'))
    
    # Upload to S3
    bucket_name = os.environ.get('REPORTS_BUCKET_NAME', 'ai-compliance-reports')
    s3_key = f"reports/{report_type}/{report_id}.json"
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=report_json,
            ContentType='application/json',
            Metadata={
                'report-id': report_id,
                'report-type': report_type,
                'generated-at': datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Generate presigned URL for download
        report_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=3600  # 1 hour
        )
        
    except ClientError as e:
        logger.error(f"Failed to upload report to S3: {str(e)}")
        raise
    
    end_time = datetime.now(timezone.utc)
    generation_time_ms = int((end_time - start_time).total_seconds() * 1000)
    
    return {
        'report_id': report_id,
        'report_url': report_url,
        'report_size_bytes': report_size_bytes,
        'generation_time_ms': generation_time_ms,
        'records_processed': report_data.get('summary', {}).get('total_records', 0)
    }

async def generate_compliance_summary_report(
    start_date: datetime,
    end_date: datetime,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate compliance summary report"""
    
    # Get audit statistics
    stats = await database.get_audit_statistics(start_date, end_date)
    
    # Calculate compliance metrics
    total_events = stats.get('total_events', 0)
    policy_violations = stats.get('policy_violations', 0)
    compliance_rate = ((total_events - policy_violations) / total_events * 100) if total_events > 0 else 100
    
    # Get event type breakdown
    events_by_type = stats.get('events_by_type', {})
    
    # Calculate processing metrics
    avg_processing_time = stats.get('average_processing_time', 0)
    total_cost = stats.get('total_cost', 0.0)
    
    return {
        'summary': {
            'total_records': total_events,
            'compliance_rate_percent': round(compliance_rate, 2),
            'policy_violations': policy_violations,
            'average_processing_time_ms': round(avg_processing_time, 2),
            'total_cost_usd': round(total_cost, 4)
        },
        'event_breakdown': events_by_type,
        'compliance_metrics': {
            'approved_content': total_events - policy_violations,
            'rejected_content': policy_violations,
            'approval_rate_percent': round(compliance_rate, 2),
            'rejection_rate_percent': round((policy_violations / total_events * 100) if total_events > 0 else 0, 2)
        },
        'performance_metrics': {
            'total_processing_time_ms': total_events * avg_processing_time if total_events > 0 else 0,
            'average_processing_time_ms': avg_processing_time,
            'cost_per_event_usd': round((total_cost / total_events) if total_events > 0 else 0, 6)
        }
    }

async def generate_policy_violations_report(
    start_date: datetime,
    end_date: datetime,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate policy violations report"""
    
    # Query policy decision events
    policy_events = await database.query_audit_events_by_type(EventType.POLICY_DECISION, limit=1000)
    
    # Filter by date range
    filtered_events = [
        event for event in policy_events
        if start_date <= event.timestamp <= end_date
    ]
    
    # Filter by product_id if specified
    if product_id:
        filtered_events = [event for event in filtered_events if event.product_id == product_id]
    
    # Filter by user_id if specified
    if user_id:
        filtered_events = [event for event in filtered_events if event.user_id == user_id]
    
    # Analyze violations
    violations = []
    violation_types = {}
    products_affected = set()
    users_affected = set()
    
    for event in filtered_events:
        if event.policy_decision and not event.policy_decision.get('approved', True):
            violation_reasons = event.policy_decision.get('policy_violations', [])
            
            violations.append({
                'event_id': event.audit_id,
                'timestamp': event.timestamp.isoformat(),
                'review_id': event.review_id,
                'user_id': event.user_id,
                'product_id': event.product_id,
                'violation_reasons': violation_reasons,
                'analysis_scores': {
                    'toxicity': event.analysis_results.get('toxicity_score', 0) if event.analysis_results else 0,
                    'bias': event.analysis_results.get('bias_score', 0) if event.analysis_results else 0,
                    'hallucination': event.analysis_results.get('hallucination_score', 0) if event.analysis_results else 0
                }
            })
            
            # Count violation types
            for reason in violation_reasons:
                violation_types[reason] = violation_types.get(reason, 0) + 1
            
            products_affected.add(event.product_id)
            users_affected.add(event.user_id)
    
    return {
        'summary': {
            'total_violations': len(violations),
            'unique_products_affected': len(products_affected),
            'unique_users_affected': len(users_affected),
            'violation_types_count': len(violation_types)
        },
        'violation_breakdown': violation_types,
        'violations': violations[:100],  # Limit to first 100 for report size
        'top_violation_types': sorted(violation_types.items(), key=lambda x: x[1], reverse=True)[:10]
    }

async def generate_processing_stats_report(
    start_date: datetime,
    end_date: datetime,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate processing statistics report"""
    
    # Get audit statistics
    stats = await database.get_audit_statistics(start_date, end_date)
    
    # Query recent events for detailed analysis
    analysis_events = await database.query_audit_events_by_type(EventType.ANALYSIS, limit=1000)
    
    # Filter by date range
    filtered_events = [
        event for event in analysis_events
        if start_date <= event.timestamp <= end_date
    ]
    
    # Calculate processing statistics
    processing_times = []
    toxicity_scores = []
    bias_scores = []
    hallucination_scores = []
    
    for event in filtered_events:
        if event.processing_duration_ms > 0:
            processing_times.append(event.processing_duration_ms)
        
        if event.analysis_results:
            toxicity_scores.append(event.analysis_results.get('toxicity_score', 0))
            bias_scores.append(event.analysis_results.get('bias_score', 0))
            hallucination_scores.append(event.analysis_results.get('hallucination_score', 0))
    
    # Calculate statistics
    def calculate_stats(values):
        if not values:
            return {'min': 0, 'max': 0, 'avg': 0, 'count': 0}
        return {
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'count': len(values)
        }
    
    return {
        'summary': {
            'total_events_processed': len(filtered_events),
            'date_range_days': (end_date - start_date).days,
            'events_per_day': len(filtered_events) / max((end_date - start_date).days, 1)
        },
        'processing_performance': {
            'processing_times_ms': calculate_stats(processing_times),
            'total_cost_usd': stats.get('total_cost', 0.0),
            'average_cost_per_event': stats.get('total_cost', 0.0) / max(len(filtered_events), 1)
        },
        'content_analysis_scores': {
            'toxicity_scores': calculate_stats(toxicity_scores),
            'bias_scores': calculate_stats(bias_scores),
            'hallucination_scores': calculate_stats(hallucination_scores)
        },
        'event_type_distribution': stats.get('events_by_type', {})
    }