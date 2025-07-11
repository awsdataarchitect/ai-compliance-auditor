"""
Unit tests for Audit Logger Lambda handler
"""

import json
from unittest.mock import Mock, patch, AsyncMock
import sys
import os
from datetime import datetime, timezone

# Add the common layer to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from handler import (
    lambda_handler, create_audit_event_from_data, log_to_cloudwatch
)
from models import EventType

class TestAuditLoggerHandler:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'test-request-123'
        self.mock_context.function_name = 'audit-logger-test'
        
        self.sample_audit_event = {
            'audit_id': 'audit-123',
            'timestamp': '2024-01-01T00:00:00Z',
            'event_type': 'ANALYSIS',
            'review_id': 'review-123',
            'user_id': 'user-123',
            'product_id': 'product-123',
            'region': 'us-east-1',
            'analysis_results': {
                'toxicity_score': 2.0,
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            'policy_decision': {
                'decision': 'ALLOW',
                'reasons': ['CONTENT_APPROVED']
            },
            'processing_duration_ms': 1500
        }
    
    def test_create_audit_event_from_data(self):
        """Test creating AuditEvent from raw data"""
        audit_event = create_audit_event_from_data(self.sample_audit_event, self.mock_context)
        
        assert audit_event.audit_id == 'audit-123'
        assert audit_event.event_type == EventType.ANALYSIS
        assert audit_event.review_id == 'review-123'
        assert audit_event.analysis_results['toxicity_score'] == 2.0
    
    def test_create_audit_event_with_defaults(self):
        """Test creating AuditEvent with missing fields (uses defaults)"""
        minimal_data = {
            'event_type': 'ANALYSIS',
            'review_id': 'review-123'
        }
        
        audit_event = create_audit_event_from_data(minimal_data, self.mock_context)
        
        assert audit_event.audit_id is not None  # Should generate UUID
        assert audit_event.event_type == EventType.ANALYSIS
        assert audit_event.review_id == 'review-123'
        assert isinstance(audit_event.timestamp, datetime)
    
    def test_create_audit_event_unknown_type(self):
        """Test creating AuditEvent with unknown event type"""
        data_with_unknown_type = {
            **self.sample_audit_event,
            'event_type': 'UNKNOWN_TYPE'
        }
        
        audit_event = create_audit_event_from_data(data_with_unknown_type, self.mock_context)
        
        assert audit_event.event_type == EventType.UNKNOWN

if __name__ == "__main__":
    # Run simple tests
    test_instance = TestAuditLoggerHandler()
    test_instance.setup_method()
    
    print("Running Audit Logger Lambda tests...")
    
    # Test audit event creation
    test_instance.test_create_audit_event_from_data()
    print("✅ Audit event creation test passed")
    
    # Test audit event with defaults
    test_instance.test_create_audit_event_with_defaults()
    print("✅ Audit event defaults test passed")
    
    # Test unknown event type handling
    test_instance.test_create_audit_event_unknown_type()
    print("✅ Unknown event type test passed")
    
    print("\n🎉 All Audit Logger Lambda tests passed!")