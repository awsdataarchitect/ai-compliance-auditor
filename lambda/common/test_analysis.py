"""
Integration tests for review analysis functions.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from analysis import ReviewAnalyzer, AnalysisError
from models import Review, AnalysisResult, ReviewStatus, Region, ProductCategory
from bedrock_client import BedrockError


class TestReviewAnalyzer:
    """Test ReviewAnalyzer class."""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create a mock Bedrock client."""
        mock_client = Mock()
        
        # Mock toxicity analysis response
        mock_client.analyze_toxicity = AsyncMock(return_value={
            'toxicity_score': 3.5,
            'explanation': 'Mild negative language detected',
            'confidence': 0.8,
            'detected_issues': ['negative_sentiment'],
            'model_metadata': {'model_id': 'test-model', 'processing_time_ms': 1000}
        })
        
        # Mock bias analysis response
        mock_client.analyze_bias = AsyncMock(return_value={
            'bias_score': 1.2,
            'explanation': 'No significant bias detected',
            'confidence': 0.9,
            'bias_types': [],
            'problematic_phrases': [],
            'model_metadata': {'model_id': 'test-model', 'processing_time_ms': 1000}
        })
        
        # Mock hallucination analysis response
        mock_client.analyze_hallucination = AsyncMock(return_value={
            'hallucination_score': 2.8,
            'explanation': 'Claims appear realistic',
            'confidence': 0.85,
            'questionable_claims': [],
            'realistic_claims': ['good build quality', 'fast shipping'],
            'model_metadata': {'model_id': 'test-model', 'processing_time_ms': 1000}
        })
        
        return mock_client
    
    @pytest.fixture
    def analyzer(self, mock_bedrock_client):
        """Create ReviewAnalyzer with mocked Bedrock client."""
        with patch('analysis.bedrock_client', mock_bedrock_client):
            return ReviewAnalyzer()
    
    @pytest.mark.asyncio
    async def test_analyze_toxicity(self, analyzer):
        """Test toxicity analysis."""
        content = "This product is terrible and a waste of money."
        
        result = await analyzer.analyze_toxicity(content)
        
        assert 'toxicity_score' in result
        assert 'explanation' in result
        assert 'confidence' in result
        assert 'detected_issues' in result
        assert 'threshold_exceeded' in result
        assert 'model_metadata' in result
        
        assert isinstance(result['toxicity_score'], float)
        assert 0 <= result['toxicity_score'] <= 10
        assert isinstance(result['threshold_exceeded'], bool)
    
    @pytest.mark.asyncio
    async def test_analyze_bias(self, analyzer):
        """Test bias analysis."""
        content = "Good product for the price range."
        
        result = await analyzer.analyze_bias(content)
        
        assert 'bias_score' in result
        assert 'explanation' in result
        assert 'confidence' in result
        assert 'bias_types' in result
        assert 'problematic_phrases' in result
        assert 'threshold_exceeded' in result
        assert 'model_metadata' in result
        
        assert isinstance(result['bias_score'], float)
        assert 0 <= result['bias_score'] <= 10
    
    @pytest.mark.asyncio
    async def test_analyze_hallucination(self, analyzer):
        """Test hallucination analysis."""
        content = "Great build quality and fast shipping."
        
        result = await analyzer.analyze_hallucination(content)
        
        assert 'hallucination_score' in result
        assert 'explanation' in result
        assert 'confidence' in result
        assert 'questionable_claims' in result
        assert 'realistic_claims' in result
        assert 'threshold_exceeded' in result
        assert 'model_metadata' in result
        
        assert isinstance(result['hallucination_score'], float)
        assert 0 <= result['hallucination_score'] <= 10
    
    @pytest.mark.asyncio
    async def test_comprehensive_analysis(self, analyzer):
        """Test comprehensive analysis."""
        content = "Good product with decent build quality."
        
        result = await analyzer.comprehensive_analysis(content)
        
        assert isinstance(result, AnalysisResult)
        assert hasattr(result, 'toxicity_score')
        assert hasattr(result, 'bias_score')
        assert hasattr(result, 'hallucination_score')
        assert hasattr(result, 'explanations')
        assert hasattr(result, 'confidence_scores')
        
        # Check that all scores are within valid range
        assert 0 <= result.toxicity_score <= 10
        assert 0 <= result.bias_score <= 10
        assert 0 <= result.hallucination_score <= 10
        
        # Check explanations
        assert 'toxicity' in result.explanations
        assert 'bias' in result.explanations
        assert 'hallucination' in result.explanations
    
    @pytest.mark.asyncio
    async def test_comprehensive_analysis_with_bedrock_error(self, analyzer, mock_bedrock_client):
        """Test comprehensive analysis with Bedrock error."""
        mock_bedrock_client.analyze_toxicity.side_effect = BedrockError("Service unavailable")
        
        with pytest.raises(AnalysisError):
            await analyzer.comprehensive_analysis("Test content")
    
    @pytest.mark.asyncio
    async def test_batch_analysis(self, analyzer):
        """Test batch analysis of multiple reviews."""
        reviews = [
            "Great product, highly recommend!",
            "Decent quality for the price.",
            "Not worth the money, poor build quality."
        ]
        
        results = await analyzer.batch_analysis(reviews, max_concurrent=2)
        
        assert len(results) == len(reviews)
        for result in results:
            assert isinstance(result, AnalysisResult)
            assert 0 <= result.toxicity_score <= 10
            assert 0 <= result.bias_score <= 10
            assert 0 <= result.hallucination_score <= 10
    
    @pytest.mark.asyncio
    async def test_batch_analysis_with_failures(self, analyzer, mock_bedrock_client):
        """Test batch analysis with some failures."""
        reviews = ["Good product", "Bad product"]
        
        # Make the second analysis fail
        call_count = 0
        async def mock_analyze_toxicity(content):
            nonlocal call_count
            call_count += 1
            if call_count > 3:  # Fail on second comprehensive analysis (3 calls per analysis)
                raise BedrockError("Service error")
            return {
                'toxicity_score': 2.0,
                'explanation': 'Low toxicity',
                'confidence': 0.8,
                'detected_issues': [],
                'model_metadata': {'model_id': 'test-model'}
            }
        
        mock_bedrock_client.analyze_toxicity = mock_analyze_toxicity
        
        results = await analyzer.batch_analysis(reviews)
        
        assert len(results) == 2
        # First should succeed, second should have default values due to failure
        assert results[0].toxicity_score > 0  # Successful analysis
        assert results[1].toxicity_score == 0  # Failed analysis default
    
    def test_get_analysis_summary(self, analyzer):
        """Test analysis summary generation."""
        analysis_result = AnalysisResult(
            toxicity_score=6.5,
            bias_score=2.1,
            hallucination_score=3.8,
            explanations={
                'toxicity': 'High toxicity detected',
                'bias': 'Low bias',
                'hallucination': 'Some questionable claims'
            },
            confidence_scores={
                'toxicity': 0.9,
                'bias': 0.8,
                'hallucination': 0.7
            }
        )
        
        summary = analyzer.get_analysis_summary(analysis_result)
        
        assert 'risk_level' in summary
        assert 'max_score' in summary
        assert 'threshold_violations' in summary
        assert 'should_approve' in summary
        assert 'scores' in summary
        assert 'confidence_scores' in summary
        
        assert summary['max_score'] == 6.5
        assert summary['risk_level'] == 'MEDIUM'  # Score 6.5 should be MEDIUM risk
        assert not summary['should_approve']  # Should not approve due to high toxicity
        assert len(summary['threshold_violations']) > 0  # Should have toxicity violation
    
    def test_get_analysis_summary_low_risk(self, analyzer):
        """Test analysis summary for low-risk content."""
        analysis_result = AnalysisResult(
            toxicity_score=1.5,
            bias_score=0.8,
            hallucination_score=2.2,
            explanations={
                'toxicity': 'Very low toxicity',
                'bias': 'No bias detected',
                'hallucination': 'All claims appear realistic'
            }
        )
        
        summary = analyzer.get_analysis_summary(analysis_result)
        
        assert summary['risk_level'] == 'MINIMAL'
        assert summary['should_approve'] is True
        assert len(summary['threshold_violations']) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_review_object(self, analyzer):
        """Test analyzing a Review object."""
        review = Review(
            product_id='prod-123',
            user_id='user-456',
            content='Great product with excellent build quality!',
            rating=5,
            region=Region.US_EAST_1,
            product_category=ProductCategory.ELECTRONICS
        )
        
        analyzed_review = await analyzer.analyze_review_object(review)
        
        assert analyzed_review.analysis_result is not None
        assert isinstance(analyzed_review.analysis_result, AnalysisResult)
        assert analyzed_review.review_id == review.review_id
        
        # Check that analysis results are populated
        assert analyzed_review.analysis_result.toxicity_score >= 0
        assert analyzed_review.analysis_result.bias_score >= 0
        assert analyzed_review.analysis_result.hallucination_score >= 0
    
    @pytest.mark.asyncio
    async def test_analyze_review_object_with_error(self, analyzer, mock_bedrock_client):
        """Test analyzing a Review object with analysis error."""
        mock_bedrock_client.analyze_toxicity.side_effect = BedrockError("Analysis failed")
        
        review = Review(
            product_id='prod-123',
            user_id='user-456',
            content='Test content',
            rating=3,
            region=Region.US_EAST_1,
            product_category=ProductCategory.ELECTRONICS
        )
        
        with pytest.raises(AnalysisError):
            await analyzer.analyze_review_object(review)
        
        # Check that error was recorded
        assert len(review.processing_errors) > 0
        assert 'Analysis failed' in review.processing_errors[0]
    
    def test_get_thresholds(self, analyzer):
        """Test getting current thresholds."""
        thresholds = analyzer.get_thresholds()
        
        assert 'toxicity_threshold' in thresholds
        assert 'bias_threshold' in thresholds
        assert 'hallucination_threshold' in thresholds
        
        assert isinstance(thresholds['toxicity_threshold'], float)
        assert isinstance(thresholds['bias_threshold'], float)
        assert isinstance(thresholds['hallucination_threshold'], float)
    
    def test_update_thresholds(self, analyzer):
        """Test updating analysis thresholds."""
        original_thresholds = analyzer.get_thresholds()
        
        # Update thresholds
        analyzer.update_thresholds(toxicity=7.0, bias=4.0, hallucination=8.0)
        
        updated_thresholds = analyzer.get_thresholds()
        
        assert updated_thresholds['toxicity_threshold'] == 7.0
        assert updated_thresholds['bias_threshold'] == 4.0
        assert updated_thresholds['hallucination_threshold'] == 8.0
        
        # Test boundary conditions
        analyzer.update_thresholds(toxicity=-1.0, bias=15.0)  # Should be clamped
        
        final_thresholds = analyzer.get_thresholds()
        assert final_thresholds['toxicity_threshold'] == 0.0  # Clamped to minimum
        assert final_thresholds['bias_threshold'] == 10.0  # Clamped to maximum
    
    def test_score_validation(self, analyzer, mock_bedrock_client):
        """Test that scores are properly validated and normalized."""
        # Mock response with out-of-range scores
        mock_bedrock_client.analyze_toxicity = AsyncMock(return_value={
            'toxicity_score': 15.0,  # Out of range
            'explanation': 'Test',
            'confidence': 1.5,  # Out of range
            'detected_issues': [],
            'model_metadata': {}
        })
        
        result = asyncio.run(analyzer.analyze_toxicity("test content"))
        
        # Score should be clamped to valid range
        assert 0 <= result['toxicity_score'] <= 10
        assert result['toxicity_score'] == 10.0  # Should be clamped to max


class TestAnalysisErrorHandling:
    """Test error handling in analysis functions."""
    
    @pytest.mark.asyncio
    async def test_bedrock_error_handling(self):
        """Test handling of Bedrock errors."""
        with patch('analysis.bedrock_client') as mock_client:
            mock_client.analyze_toxicity.side_effect = BedrockError("Service error")
            
            analyzer = ReviewAnalyzer()
            
            with pytest.raises(AnalysisError) as exc_info:
                await analyzer.analyze_toxicity("test content")
            
            assert "Failed to analyze toxicity" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test handling of unexpected errors."""
        with patch('analysis.bedrock_client') as mock_client:
            mock_client.analyze_bias.side_effect = ValueError("Unexpected error")
            
            analyzer = ReviewAnalyzer()
            
            with pytest.raises(AnalysisError) as exc_info:
                await analyzer.analyze_bias("test content")
            
            assert "Unexpected error in bias analysis" in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__])