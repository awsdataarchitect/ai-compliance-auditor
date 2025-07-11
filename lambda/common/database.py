"""
Database utilities for DynamoDB operations.
"""
import boto3
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from botocore.exceptions import ClientError
import logging
from decimal import Decimal

from models import Review, AuditEvent, ReviewSummary, EventType
from config import AUDIT_TABLE_NAME, AWS_REGION

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types from DynamoDB."""
    
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


class DatabaseClient:
    """DynamoDB client for AI Compliance Auditor operations."""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        self.audit_table = self.dynamodb.Table(AUDIT_TABLE_NAME or 'ai-compliance-audit-logs')
        self.reviews_table = self.dynamodb.Table('ai-compliance-reviews')
        self.summaries_table = self.dynamodb.Table('ai-compliance-summaries')
    
    # Audit Events Operations
    async def put_audit_event(self, event: AuditEvent) -> bool:
        """Store an audit event in DynamoDB."""
        try:
            item = event.to_dynamodb_item()
            self.audit_table.put_item(Item=item)
            logger.info(f"Stored audit event: {event.audit_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to store audit event {event.audit_id}: {str(e)}")
            return False
    
    async def batch_put_audit_events(self, events: List[AuditEvent]) -> int:
        """Batch store multiple audit events."""
        success_count = 0
        
        # DynamoDB batch_writer handles batching automatically
        with self.audit_table.batch_writer() as batch:
            for event in events:
                try:
                    item = event.to_dynamodb_item()
                    batch.put_item(Item=item)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to batch write audit event {event.audit_id}: {str(e)}")
        
        logger.info(f"Batch stored {success_count}/{len(events)} audit events")
        return success_count
    
    async def get_audit_event(self, audit_id: str, timestamp: str) -> Optional[AuditEvent]:
        """Retrieve an audit event by ID and timestamp."""
        try:
            response = self.audit_table.get_item(
                Key={
                    'audit_id': audit_id,
                    'timestamp': timestamp
                }
            )
            
            if 'Item' in response:
                return AuditEvent.from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Failed to get audit event {audit_id}: {str(e)}")
            return None
    
    async def query_audit_events_by_review(self, review_id: str, limit: int = 50) -> List[AuditEvent]:
        """Query audit events for a specific review."""
        try:
            response = self.audit_table.query(
                IndexName='review-id-index',
                KeyConditionExpression='review_id = :review_id',
                ExpressionAttributeValues={':review_id': review_id},
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            events = []
            for item in response.get('Items', []):
                events.append(AuditEvent.from_dynamodb_item(item))
            
            return events
        except ClientError as e:
            logger.error(f"Failed to query audit events for review {review_id}: {str(e)}")
            return []
    
    async def query_audit_events_by_user(self, user_id: str, limit: int = 100) -> List[AuditEvent]:
        """Query audit events for a specific user."""
        try:
            response = self.audit_table.query(
                IndexName='user-id-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=limit,
                ScanIndexForward=False
            )
            
            events = []
            for item in response.get('Items', []):
                events.append(AuditEvent.from_dynamodb_item(item))
            
            return events
        except ClientError as e:
            logger.error(f"Failed to query audit events for user {user_id}: {str(e)}")
            return []
    
    async def query_audit_events_by_product(self, product_id: str, limit: int = 100) -> List[AuditEvent]:
        """Query audit events for a specific product."""
        try:
            response = self.audit_table.query(
                IndexName='product-id-index',
                KeyConditionExpression='product_id = :product_id',
                ExpressionAttributeValues={':product_id': product_id},
                Limit=limit,
                ScanIndexForward=False
            )
            
            events = []
            for item in response.get('Items', []):
                events.append(AuditEvent.from_dynamodb_item(item))
            
            return events
        except ClientError as e:
            logger.error(f"Failed to query audit events for product {product_id}: {str(e)}")
            return []
    
    async def query_audit_events_by_type(self, event_type: EventType, limit: int = 100) -> List[AuditEvent]:
        """Query audit events by event type."""
        try:
            response = self.audit_table.query(
                IndexName='event-type-index',
                KeyConditionExpression='event_type = :event_type',
                ExpressionAttributeValues={':event_type': event_type.value},
                Limit=limit,
                ScanIndexForward=False
            )
            
            events = []
            for item in response.get('Items', []):
                events.append(AuditEvent.from_dynamodb_item(item))
            
            return events
        except ClientError as e:
            logger.error(f"Failed to query audit events by type {event_type}: {str(e)}")
            return []
    
    # Reviews Operations
    async def put_review(self, review: Review) -> bool:
        """Store a review in DynamoDB."""
        try:
            item = review.to_dynamodb_item()
            self.reviews_table.put_item(Item=item)
            logger.info(f"Stored review: {review.review_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to store review {review.review_id}: {str(e)}")
            return False
    
    async def get_review(self, review_id: str) -> Optional[Review]:
        """Retrieve a review by ID."""
        try:
            response = self.reviews_table.get_item(
                Key={'review_id': review_id}
            )
            
            if 'Item' in response:
                return Review.from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Failed to get review {review_id}: {str(e)}")
            return None
    
    async def query_reviews_by_product(self, product_id: str, limit: int = 100) -> List[Review]:
        """Query reviews for a specific product."""
        try:
            response = self.reviews_table.query(
                IndexName='product-id-index',
                KeyConditionExpression='product_id = :product_id',
                ExpressionAttributeValues={':product_id': product_id},
                Limit=limit,
                ScanIndexForward=False
            )
            
            reviews = []
            for item in response.get('Items', []):
                reviews.append(Review.from_dynamodb_item(item))
            
            return reviews
        except ClientError as e:
            logger.error(f"Failed to query reviews for product {product_id}: {str(e)}")
            return []
    
    async def query_reviews_by_user(self, user_id: str, limit: int = 50) -> List[Review]:
        """Query reviews for a specific user."""
        try:
            response = self.reviews_table.query(
                IndexName='user-id-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=limit,
                ScanIndexForward=False
            )
            
            reviews = []
            for item in response.get('Items', []):
                reviews.append(Review.from_dynamodb_item(item))
            
            return reviews
        except ClientError as e:
            logger.error(f"Failed to query reviews for user {user_id}: {str(e)}")
            return []
    
    async def query_reviews_by_status(self, status: str, limit: int = 100) -> List[Review]:
        """Query reviews by processing status."""
        try:
            response = self.reviews_table.query(
                IndexName='status-index',
                KeyConditionExpression='status = :status',
                ExpressionAttributeValues={':status': status},
                Limit=limit,
                ScanIndexForward=False
            )
            
            reviews = []
            for item in response.get('Items', []):
                reviews.append(Review.from_dynamodb_item(item))
            
            return reviews
        except ClientError as e:
            logger.error(f"Failed to query reviews by status {status}: {str(e)}")
            return []
    
    async def update_review_status(self, review_id: str, status: str, processing_errors: Optional[List[str]] = None) -> bool:
        """Update review processing status."""
        try:
            update_expression = "SET #status = :status"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {":status": status}
            
            if processing_errors:
                update_expression += ", processing_errors = :errors"
                expression_attribute_values[":errors"] = processing_errors
            
            self.reviews_table.update_item(
                Key={'review_id': review_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            
            logger.info(f"Updated review {review_id} status to {status}")
            return True
        except ClientError as e:
            logger.error(f"Failed to update review {review_id} status: {str(e)}")
            return False
    
    # Summaries Operations
    async def put_summary(self, summary: ReviewSummary) -> bool:
        """Store a review summary in DynamoDB."""
        try:
            item = summary.to_dynamodb_item()
            self.summaries_table.put_item(Item=item)
            logger.info(f"Stored summary: {summary.summary_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to store summary {summary.summary_id}: {str(e)}")
            return False
    
    async def get_summary(self, summary_id: str) -> Optional[ReviewSummary]:
        """Retrieve a summary by ID."""
        try:
            response = self.summaries_table.get_item(
                Key={'summary_id': summary_id}
            )
            
            if 'Item' in response:
                # Convert DynamoDB item back to ReviewSummary
                item = response['Item']
                return ReviewSummary(
                    summary_id=item['summary_id'],
                    product_id=item['product_id'],
                    summary_text=item['summary_text'],
                    reviews_processed=int(item['reviews_processed']),
                    reviews_excluded=int(item['reviews_excluded']),
                    exclusion_reasons=item.get('exclusion_reasons', []),
                    summary_quality_score=float(item['summary_quality_score']) if 'summary_quality_score' in item else None,
                    factual_accuracy_score=float(item['factual_accuracy_score']) if 'factual_accuracy_score' in item else None,
                    generated_at=datetime.fromisoformat(item['generated_at']),
                    policy_constraints=item.get('policy_constraints', {}),
                    model_metadata=item.get('model_metadata')
                )
            return None
        except ClientError as e:
            logger.error(f"Failed to get summary {summary_id}: {str(e)}")
            return None
    
    async def query_summaries_by_product(self, product_id: str, limit: int = 10) -> List[ReviewSummary]:
        """Query summaries for a specific product."""
        try:
            response = self.summaries_table.query(
                IndexName='product-id-index',
                KeyConditionExpression='product_id = :product_id',
                ExpressionAttributeValues={':product_id': product_id},
                Limit=limit,
                ScanIndexForward=False
            )
            
            summaries = []
            for item in response.get('Items', []):
                summary = ReviewSummary(
                    summary_id=item['summary_id'],
                    product_id=item['product_id'],
                    summary_text=item['summary_text'],
                    reviews_processed=int(item['reviews_processed']),
                    reviews_excluded=int(item['reviews_excluded']),
                    exclusion_reasons=item.get('exclusion_reasons', []),
                    summary_quality_score=float(item['summary_quality_score']) if 'summary_quality_score' in item else None,
                    factual_accuracy_score=float(item['factual_accuracy_score']) if 'factual_accuracy_score' in item else None,
                    generated_at=datetime.fromisoformat(item['generated_at']),
                    policy_constraints=item.get('policy_constraints', {}),
                    model_metadata=item.get('model_metadata')
                )
                summaries.append(summary)
            
            return summaries
        except ClientError as e:
            logger.error(f"Failed to query summaries for product {product_id}: {str(e)}")
            return []
    
    # Analytics and Reporting Operations
    async def get_audit_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get audit statistics for a date range."""
        try:
            # This would typically use DynamoDB's scan operation with filters
            # For production, consider using DynamoDB Streams + Lambda to maintain aggregated statistics
            
            stats = {
                'total_events': 0,
                'events_by_type': {},
                'policy_violations': 0,
                'average_processing_time': 0,
                'total_cost': 0.0
            }
            
            # Scan audit table for the date range (expensive operation - consider alternatives)
            response = self.audit_table.scan(
                FilterExpression='#ts BETWEEN :start_date AND :end_date',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_date': start_date.isoformat(),
                    ':end_date': end_date.isoformat()
                }
            )
            
            total_processing_time = 0
            for item in response.get('Items', []):
                stats['total_events'] += 1
                
                event_type = item.get('event_type', 'UNKNOWN')
                stats['events_by_type'][event_type] = stats['events_by_type'].get(event_type, 0) + 1
                
                if 'policy_decision' in item and not item['policy_decision'].get('approved', True):
                    stats['policy_violations'] += 1
                
                processing_time = item.get('processing_duration_ms', 0)
                total_processing_time += processing_time
                
                if 'model_metadata' in item and 'cost_usd' in item['model_metadata']:
                    stats['total_cost'] += float(item['model_metadata']['cost_usd'])
            
            if stats['total_events'] > 0:
                stats['average_processing_time'] = total_processing_time / stats['total_events']
            
            return stats
        except ClientError as e:
            logger.error(f"Failed to get audit statistics: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, bool]:
        """Check the health of all database connections."""
        health = {
            'audit_table': False,
            'reviews_table': False,
            'summaries_table': False
        }
        
        try:
            # Test audit table
            self.audit_table.meta.client.describe_table(TableName=self.audit_table.name)
            health['audit_table'] = True
        except Exception as e:
            logger.error(f"Audit table health check failed: {str(e)}")
        
        try:
            # Test reviews table
            self.reviews_table.meta.client.describe_table(TableName=self.reviews_table.name)
            health['reviews_table'] = True
        except Exception as e:
            logger.error(f"Reviews table health check failed: {str(e)}")
        
        try:
            # Test summaries table
            self.summaries_table.meta.client.describe_table(TableName=self.summaries_table.name)
            health['summaries_table'] = True
        except Exception as e:
            logger.error(f"Summaries table health check failed: {str(e)}")
        
        return health


# Global database client instance
db_client = DatabaseClient()