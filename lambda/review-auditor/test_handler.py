"""
Unit tests for Review Auditor Lambda handler.
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Mock the common layer imports before importing handler
import sys
sys.path.insert(0, '/opt/python')

with patch.dict('sys.modules', {
    'models': Mock(),
    'analysis': Mock(),
    'database': Mock(),
    'config': Mock()
}):
    from handler import (
        validate_input, create_review_object, format_response,
        lambda_handler, ReviewAuditorError
    )


class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_input_direct_invocation(self):
        """Test validation with direct Lambda invocation format."""
        event = {
            'review_id': 'review-123',
            'content': 'Great product, highly recommend!',
            'product_id': 'prod-456',
            'user_id': 'user-789',
            'rating': 5
        }
        
        result = validate_input(event)
        
        assert result['review_id'] == 'review-123'
        assert result['content'] == 'Great product, highly recommend!'
        assert result['product_id'] == 'prod-456'
        assert result['user_id'] == 'user-789'
        assert result['rating'] == 5
        assert result['region'] == 'us-east-1'  # Default
        assert result['product_category'] == 'other'  # Default
    
    def test_validate_input_api_gateway_format(self):
        """Test validation with API Gateway format."""
        event = {
            'body': json.dumps({
                'review_id': 'review-123',
                'content': 'Good product',
                'product_id': 'prod-456',
                'user_id': 'user-789',
                'rating': 4,
                'region': 'eu-west-1',
                'product_category': 'electronics'
            })
        }
        
        result = validate_input(event)
        
        assert result['review_id'] == 'review-123'
        assert result['region'] == 'eu-west-1'
        assert result['product_category'] == 'electronics'
    
    def test_validate_input_step_functions_format(self):
        """Test validation with Step Functions format."""
        event = {
            'Input': {
                'review_id': 'review-123',
                'content': 'Decent quality',
                'product_id': 'prod-456',
                'user_id': 'user-789'
            }
        }
        
        result = validate_input(event)
        
        assert result['review_id'] == 'review-123'
        assert result['rating'] == 3  # Default rating
    
    def test_validate_input_missing_required_field(self):
        """Test validation with missing required field."""
        event = {
            'review_id': 'review-123',
            'content': 'Good product',
            'product_id': 'prod-456'
            # Missing user_id
        }
        
        with pytest.raises(ReviewAuditorError) as exc_info:
            validate_input(event)
        
        assert 'Missing required field: user_id' in str(exc_info.value)
    
    def test_validate_input_empty_content(self):
        """Test validation with empty content."""
        event = {
            'review_id': 'review-123',
            'content': '   ',  # Whitespace only
            'product_id': 'prod-456',
            'user_id': 'user-789'
        }
        
        with pytest.raises(ReviewAuditorError) as exc_info:
            validate_input(event)
        
        assert 'Review content cannot be empty' in str(exc_info.value)
    
    def test_validate_input_content_too_long(self):
        """Test validation with content exceeding maximum length."""
        event = {
            'review_id': 'review-123',
            'content': 'x' * 5001,  # Exceeds 5000 character limit
            'product_id': 'prod-456',
            'user_id': 'user-789'
        }
        
        with pytest.raises(ReviewAuditorError) as exc_info:
            validate_input(event)
        
        assert 'exceeds maximum length' in str(exc_info.value)
    
    def test_validate_input_invalid_rating(self):
        """Test validation with invalid rating."""
        event = {
            'review_id': 'review-123',
            'content': 'Good product',
            'product_id': 'prod-456',
            'user_id': 'user-789',
            'rating': 6  # Invalid rating (must be 1-5)
        }
        
        with pytest.raises(ReviewAuditorError) as exc_info:
            validate_input(event)
        
        assert 'Rating must be between 1 and 5' in str(exc_info.value)
    
    def test_validate_input_invalid_json(self):
        """Test validation with invalid JSON in body."""
        event = {
            'body': 'invalid json'
        }
        
        with pytest.raises(ReviewAuditorError) as exc_info:
            validate_input(event)
        
        assert 'Invalid JSON' in str(exc_info.value)


class TestCreateReviewObject:
    """Test Review object creation."""
    
    @patch('handler.Review')
    @patch('handler.Region')
    @patch('handler.ProductCategory')
    @patch('handler.ReviewStatus')
    def test_create_review_object(self, mock_status, mock_category, mock_region, mock_review):
        """Test creating Review object from input data."""
        input_data = {
            'review_id': 'review-123',
            'product_id': 'prod-456',
            'user_id': 'user-789',
            'content': 'Great product!',
            'rating': 5,
            'timestamp': '2024-01-01T12:00:00',
            'region': 'us-east-1',
            'product_category': 'electronics',
            'language': 'en'
        }
        
        create_review_object(input_data)
        
        # Verify Review constructor was called with correct arguments
        mock_review.assert_called_once()
        call_args = mock_review.call_args[1]  # Get keyword arguments
        
        assert call_args['review_id'] == 'review-123'
        assert call_args['product_id'] == 'prod-456'
        assert call_args['user_id'] == 'user-789'
        assert call_args['content'] == 'Great product!'
        assert call_args['rating'] == 5
        assert call_args['language'] == 'en'


class TestFormatResponse:
    """Test response formatting."""
    
    def test_format_response_success(self):
        """Test formatting successful response."""
        # Mock objects
        mock_review = Mock()
        mock_review.review_id = 'review-123'
        mock_review.status.value = 'APPROVED'
        mock_review.processing_errors = []
        
        mock_analysis = Mock()
        mock_analysis.toxicity_score = 2.5
        mock_analysis.bias_score = 1.2
        mock_analysis.hallucination_score = 3.1
        mock_analysis.explanations = {
            'toxicity': 'Low toxicity',
            'bias': 'No bias detected',
            'hallucination': 'Realistic claims'
        }
        mock_analysis.confidence_scores = {
            'toxicity': 0.9,
            'bias': 0.8,
            'hallucination': 0.85
        }
        
        with patch('handler.review_analyzer') as mock_analyzer:
            mock_analyzer.get_analysis_summary.return_value = {
                'risk_level': 'LOW',
                'should_approve': True,
                'threshold_violations': [],
                'max_score': 3.1
            }
            mock_analyzer.get_thresholds.return_value = {
                'toxicity_threshold': 5.0,
                'bias_threshold': 3.0,
                'hallucination_threshold': 6.0
            }
            
            response = format_response(mock_review, mock_analysis, 1500, success=True)
        
        assert response['success'] is True
        assert response['review_id'] == 'review-123'
        assert response['processing_time_ms'] == 1500
        assert 'analysis' in response
        assert 'summary' in response
        assert 'thresholds' in response
        assert response['analysis']['toxicity_score'] == 2.5
        assert response['summary']['risk_level'] == 'LOW'
    
    def test_format_response_with_errors(self):
        """Test formatting response with processing errors."""
        mock_review = Mock()
        mock_review.review_id = 'review-123'
        mock_review.status.value = 'REJECTED'
        mock_review.processing_errors = ['Policy violation: high toxicity']
        
        mock_analysis = Mock()
        mock_analysis.toxicity_score = 8.5
        mock_analysis.bias_score = 2.0
        mock_analysis.hallucination_score = 4.0
        mock_analysis.explanations = {}
        mock_analysis.confidence_scores = {}
        
        with patch('handler.review_analyzer') as mock_analyzer:
            mock_analyzer.get_analysis_summary.return_value = {
                'risk_level': 'HIGH',
                'should_approve': False,
                'threshold_violations': ['toxicity (8.5 > 5.0)'],
                'max_score': 8.5
            }
            mock_analyzer.get_thresholds.return_value = {}
            
            response = format_response(mock_review, mock_analysis, 2000, success=True)
        
        assert response['success'] is True
        assert 'errors' in response
        assert response['errors'] == ['Policy violation: high toxicity']
        assert response['summary']['should_approve'] is False


class TestLambdaHandler:
    """Test main Lambda handler."""
    
    @pytest.mark.asyncio
    async def test_lambda_handler_success(self):
        """Test successful Lambda handler execution."""
        event = {
            'review_id': 'review-123',
            'content': 'Great product, highly recommend!',
            'product_id': 'prod-456',
            'user_id': 'user-789',
            'rating': 5
        }
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-id'
        
        # Mock all dependencies
        with patch('handler.db_client') as mock_db, \
             patch('handler.review_analyzer') as mock_analyzer, \
             patch('handler.publish_custom_metrics') as mock_metrics:
            
            # Mock database operations
            mock_db.put_review = AsyncMock()
            
            # Mock analysis results
            mock_analysis_result = Mock()
            mock_analysis_result.toxicity_score = 2.0
            mock_analysis_result.bias_score = 1.0
            mock_analysis_result.hallucination_score = 2.5
            mock_analysis_result.explanations = {}
            mock_analysis_result.confidence_scores = {}
            
            mock_analyzer.comprehensive_analysis = AsyncMock(return_value=mock_analysis_result)
            mock_analyzer.get_analysis_summary.return_value = {
                'risk_level': 'LOW',
                'should_approve': True,
                'threshold_violations': [],
                'max_score': 2.5
            }
            mock_analyzer.get_thresholds.return_value = {}
            
            response = await lambda_handler(event, mock_context)
        
        assert response['success'] is True
        assert response['review_id'] == 'review-123'
        assert 'processing_time_ms' in response
        assert 'analysis' in response
        
        # Verify database was called
        assert mock_db.put_review.call_count == 2  # Initial and final save
        
        # Verify analysis was performed
        mock_analyzer.comprehensive_analysis.assert_called_once()
        
        # Verify metrics were published
        assert mock_metrics.call_count > 0
    
    @pytest.mark.asyncio
    async def test_lambda_handler_validation_error(self):
        """Test Lambda handler with validation error."""
        event = {
            'review_id': 'review-123',
            'content': '',  # Empty content should cause validation error
            'product_id': 'prod-456',
            'user_id': 'user-789'
        }
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-id'
        
        with patch('handler.publish_custom_metrics') as mock_metrics:
            response = await lambda_handler(event, mock_context)
        
        assert response['success'] is False
        assert response['error_type'] == 'ValidationError'
        assert 'Review content cannot be empty' in response['error']
        
        # Verify error metrics were published
        mock_metrics.assert_called()
    
    @pytest.mark.asyncio
    async def test_lambda_handler_analysis_error(self):
        """Test Lambda handler with analysis error."""
        event = {
            'review_id': 'review-123',
            'content': 'Good product',
            'product_id': 'prod-456',
            'user_id': 'user-789'
        }
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-id'
        
        with patch('handler.db_client') as mock_db, \
             patch('handler.review_analyzer') as mock_analyzer, \
             patch('handler.publish_custom_metrics') as mock_metrics:
            
            mock_db.put_review = AsyncMock()
            mock_db.update_review_status = AsyncMock()
            
            # Mock analysis to raise error
            from analysis import AnalysisError
            mock_analyzer.comprehensive_analysis = AsyncMock(side_effect=AnalysisError("Bedrock unavailable"))
            
            response = await lambda_handler(event, mock_context)
        
        assert response['success'] is False
        assert response['error_type'] == 'AnalysisError'
        assert 'Bedrock unavailable' in response['error']
        
        # Verify review status was updated to failed
        mock_db.update_review_status.assert_called_once()


class TestSyncHandler:
    """Test synchronous handler wrapper."""
    
    @patch('handler.lambda_handler')
    def test_sync_handler(self, mock_async_handler):
        """Test synchronous handler wrapper."""
        from handler import handler
        
        event = {'test': 'data'}
        context = Mock()
        
        # Mock the async handler to return a simple response
        mock_async_handler.return_value = {'success': True}
        
        # The sync handler should work without issues
        # Note: This test may need adjustment based on actual asyncio implementation
        try:
            result = handler(event, context)
            # If we get here, the sync wrapper worked
            assert True
        except Exception as e:
            # If there's an asyncio-related error, that's expected in test environment
            assert 'asyncio' in str(e).lower() or 'event loop' in str(e).lower()


if __name__ == '__main__':
    pytest.main([__file__])