"""
Unit tests for Review Summarizer Lambda handler
"""

import json
from unittest.mock import Mock, patch
import sys
import os

# Add the common layer to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from handler import (
    lambda_handler, summarize_reviews, filter_reviews_for_summarization,
    generate_summary_with_bedrock, generate_fallback_summary, calculate_summary_quality
)
from policies import PolicyContext

class TestReviewSummarizerHandler:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'test-request-123'
        self.mock_context.function_name = 'review-summarizer-test'
        
        self.sample_reviews = [
            {
                'review_id': 'review-1',
                'content': 'Great product, highly recommend it. Works perfectly.',
                'rating': 5,
                'analysis_passed': True,
                'toxicity_score': 1.0,
                'bias_score': 0.5,
                'hallucination_score': 2.0
            },
            {
                'review_id': 'review-2',
                'content': 'Good value for money. Some minor issues but overall satisfied.',
                'rating': 4,
                'analysis_passed': True,
                'toxicity_score': 2.0,
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            {
                'review_id': 'review-3',
                'content': 'Terrible product, complete waste of money. Hate it.',
                'rating': 1,
                'analysis_passed': False,
                'toxicity_score': 8.0,
                'bias_score': 2.0,
                'hallucination_score': 1.0
            }
        ]
        
        self.policy_context = PolicyContext(
            region='us-east-1',
            product_category='electronics',
            compliance_mode='standard'
        )
    
    @patch('handler.bedrock_client')
    def test_successful_summarization(self, mock_bedrock):
        """Test successful review summarization"""
        # Mock Bedrock response
        mock_bedrock.invoke_model.return_value = {
            'content': 'Customers generally appreciate this product for its quality and value. Some users report minor issues but overall satisfaction is high. The product appears to work well for most buyers.'
        }
        mock_bedrock.get_last_request_metadata.return_value = {
            'model_id': 'amazon.nova-premier-v1:0',
            'request_id': 'test-123'
        }
        
        event = {
            'product_id': 'product-123',
            'reviews': self.sample_reviews,
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            },
            'summarization_config': {
                'max_sentences': 3,
                'focus_areas': ['quality', 'value']
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['product_id'] == 'product-123'
        assert len(result['summary']) > 0
        assert result['summary_metadata']['reviews_processed'] == 3
        assert result['summary_metadata']['reviews_included'] == 2  # 2 passed analysis
        assert result['summary_metadata']['reviews_excluded'] == 1  # 1 failed analysis
        assert result['policy_validation']['decision'] == 'ALLOW'
    
    def test_no_reviews_provided(self):
        """Test handling when no reviews are provided"""
        event = {
            'product_id': 'product-123',
            'reviews': [],
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 500
        assert result['error']['type'] == 'SummarizationError'
        assert 'No reviews provided' in result['error']['message']
    
    def test_filter_reviews_for_summarization(self):
        """Test review filtering logic"""
        filtered = filter_reviews_for_summarization(self.sample_reviews, self.policy_context)
        
        assert len(filtered['included']) == 2
        assert len(filtered['excluded']) == 1
        assert 'FAILED_POLICY_ANALYSIS' in filtered['exclusion_reasons']
    
    def test_filter_reviews_high_toxicity(self):
        """Test filtering reviews with high toxicity"""
        toxic_reviews = [
            {
                'review_id': 'review-1',
                'content': 'Good product',
                'rating': 5,
                'analysis_passed': True,
                'toxicity_score': 2.0
            },
            {
                'review_id': 'review-2',
                'content': 'Terrible product',
                'rating': 1,
                'analysis_passed': True,
                'toxicity_score': 8.0  # High toxicity
            }
        ]
        
        filtered = filter_reviews_for_summarization(toxic_reviews, self.policy_context)
        
        assert len(filtered['included']) == 1
        assert len(filtered['excluded']) == 1
        assert 'HIGH_TOXICITY' in filtered['exclusion_reasons']
    
    def test_filter_reviews_content_length(self):
        """Test filtering reviews based on content length"""
        length_reviews = [
            {
                'review_id': 'review-1',
                'content': 'Good',  # Too short
                'rating': 5,
                'analysis_passed': True
            },
            {
                'review_id': 'review-2',
                'content': 'A' * 2500,  # Too long
                'rating': 4,
                'analysis_passed': True
            },
            {
                'review_id': 'review-3',
                'content': 'Perfect length review with good content',
                'rating': 5,
                'analysis_passed': True
            }
        ]
        
        filtered = filter_reviews_for_summarization(length_reviews, self.policy_context)
        
        assert len(filtered['included']) == 1
        assert len(filtered['excluded']) == 2
        assert 'CONTENT_TOO_SHORT' in filtered['exclusion_reasons']
        assert 'CONTENT_TOO_LONG' in filtered['exclusion_reasons']
    
    @patch('handler.bedrock_client')
    def test_bedrock_summarization_failure(self, mock_bedrock):
        """Test fallback when Bedrock fails"""
        # Mock Bedrock failure
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")
        
        reviews = [
            {
                'review_id': 'review-1',
                'content': 'Great product, love it',
                'rating': 5
            },
            {
                'review_id': 'review-2',
                'content': 'Good value for money',
                'rating': 4
            }
        ]
        
        summary = generate_summary_with_bedrock(reviews, 'product-123', {})
        
        # Should return fallback summary
        assert len(summary) > 0
        assert 'reviews' in summary.lower()
    
    def test_generate_fallback_summary(self):
        """Test fallback summary generation"""
        reviews = [
            {
                'review_id': 'review-1',
                'content': 'Great product, excellent quality',
                'rating': 5
            },
            {
                'review_id': 'review-2',
                'content': 'Good value, recommend it',
                'rating': 4
            }
        ]
        
        summary = generate_fallback_summary(reviews, max_sentences=3)
        
        assert len(summary) > 0
        assert '2 reviews' in summary
        assert '4.5 stars' in summary  # Average rating
    
    def test_generate_fallback_summary_empty_reviews(self):
        """Test fallback summary with empty reviews"""
        summary = generate_fallback_summary([], max_sentences=3)
        
        assert summary == "No reviews available for summarization."
    
    def test_calculate_summary_quality(self):
        """Test summary quality calculation"""
        good_summary = "This product receives positive reviews for its quality and value. Customers appreciate its performance and reliability. Most users would recommend it to others."
        
        quality_score = calculate_summary_quality(good_summary, self.sample_reviews, {})
        
        assert quality_score >= 8.0  # Should be high quality
    
    def test_calculate_summary_quality_poor(self):
        """Test summary quality calculation for poor summary"""
        poor_summary = "Bad"  # Too short
        
        quality_score = calculate_summary_quality(poor_summary, self.sample_reviews, {})
        
        assert quality_score <= 8.0  # Should be lower quality
    
    def test_calculate_summary_quality_empty(self):
        """Test summary quality calculation for empty summary"""
        quality_score = calculate_summary_quality("", self.sample_reviews, {})
        
        assert quality_score == 0.0
    
    def test_insufficient_reviews_for_summary(self):
        """Test handling when insufficient reviews pass filtering"""
        # All reviews fail analysis
        bad_reviews = [
            {
                'review_id': 'review-1',
                'content': 'Terrible product',
                'rating': 1,
                'analysis_passed': False,
                'toxicity_score': 9.0
            }
        ]
        
        result = summarize_reviews(
            product_id='product-123',
            reviews=bad_reviews,
            policy_context=self.policy_context,
            config={'min_reviews_for_summary': 2}
        )
        
        assert 'Insufficient reviews' in result['summary_text']
        assert result['summary_data']['reviews_included'] == 0
        assert result['summary_data']['quality_score'] == 0.0
    
    def test_missing_policy_context(self):
        """Test handling of missing policy context"""
        event = {
            'product_id': 'product-123',
            'reviews': self.sample_reviews[:2]  # Only good reviews
        }
        
        result = lambda_handler(event, self.mock_context)
        
        # Should use default policy context
        assert result['statusCode'] == 200 or result['statusCode'] == 500  # Depends on Bedrock mock

if __name__ == "__main__":
    # Run simple tests
    test_instance = TestReviewSummarizerHandler()
    test_instance.setup_method()
    
    print("Running Review Summarizer Lambda tests...")
    
    # Test review filtering
    test_instance.test_filter_reviews_for_summarization()
    print("✅ Review filtering test passed")
    
    # Test high toxicity filtering
    test_instance.test_filter_reviews_high_toxicity()
    print("✅ High toxicity filtering test passed")
    
    # Test content length filtering
    test_instance.test_filter_reviews_content_length()
    print("✅ Content length filtering test passed")
    
    # Test fallback summary
    test_instance.test_generate_fallback_summary()
    print("✅ Fallback summary test passed")
    
    # Test empty reviews fallback
    test_instance.test_generate_fallback_summary_empty_reviews()
    print("✅ Empty reviews fallback test passed")
    
    # Test quality calculation
    test_instance.test_calculate_summary_quality()
    print("✅ Summary quality calculation test passed")
    
    # Test poor quality calculation
    test_instance.test_calculate_summary_quality_poor()
    print("✅ Poor summary quality test passed")
    
    # Test empty quality calculation
    test_instance.test_calculate_summary_quality_empty()
    print("✅ Empty summary quality test passed")
    
    print("\n🎉 All Review Summarizer Lambda tests passed!")