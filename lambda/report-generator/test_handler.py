"""
Unit tests for Report Generator Lambda handler
"""

import json
from unittest.mock import Mock, patch, AsyncMock
import sys
import os
from datetime import datetime, timezone

# Add the common layer to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from handler import lambda_handler, generate_compliance_summary_report

class TestReportGeneratorHandler:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'test-request-123'
        self.mock_context.function_name = 'report-generator-test'
        
        self.sample_event = {
            'report_type': 'compliance_summary',
            'start_date': '2024-01-01T00:00:00Z',
            'end_date': '2024-01-31T23:59:59Z'
        }
    
    def test_missing_dates(self):
        """Test handling of missing required dates"""
        event = {
            'report_type': 'compliance_summary'
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 500
        assert result['error']['type'] == 'ReportGenerationError'
        assert 'start_date and end_date are required' in result['error']['message']
    
    @patch('handler.database')
    def test_generate_compliance_summary_report(self, mock_database):
        """Test compliance summary report generation"""
        # Mock database response
        mock_stats = {
            'total_events': 100,
            'policy_violations': 5,
            'events_by_type': {'ANALYSIS': 80, 'POLICY_DECISION': 20},
            'average_processing_time': 1500,
            'total_cost': 0.50
        }
        mock_database.get_audit_statistics = AsyncMock(return_value=mock_stats)
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
        
        # This would normally be called via asyncio.run, but we'll test the function directly
        # In a real async test, we'd use pytest-asyncio
        import asyncio
        result = asyncio.run(generate_compliance_summary_report(start_date, end_date))
        
        assert result['summary']['total_records'] == 100
        assert result['summary']['policy_violations'] == 5
        assert result['summary']['compliance_rate_percent'] == 95.0
        assert result['event_breakdown']['ANALYSIS'] == 80

if __name__ == "__main__":
    # Run simple tests
    test_instance = TestReportGeneratorHandler()
    test_instance.setup_method()
    
    print("Running Report Generator Lambda tests...")
    
    # Test missing dates
    test_instance.test_missing_dates()
    print("✅ Missing dates validation test passed")
    
    # Test compliance summary report
    with patch('handler.database') as mock_database:
        mock_stats = {
            'total_events': 100,
            'policy_violations': 5,
            'events_by_type': {'ANALYSIS': 80, 'POLICY_DECISION': 20},
            'average_processing_time': 1500,
            'total_cost': 0.50
        }
        mock_database.get_audit_statistics = AsyncMock(return_value=mock_stats)
        test_instance.test_generate_compliance_summary_report()
        print("✅ Compliance summary report test passed")
    
    print("\n🎉 All Report Generator Lambda tests passed!")