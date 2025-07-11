"""
Unit tests for data models.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError
import json

from models import (
    Review, ReviewSummary, AuditEvent, AnalysisResult, ModelMetadata, PolicyDecision,
    ReviewStatus, EventType, ProductCategory, Region,
    serialize_for_json, deserialize_from_json
)


class TestAnalysisResult:
    """Test AnalysisResult model."""
    
    def test_valid_analysis_result(self):
        """Test creating a valid analysis result."""
        result = AnalysisResult(
            toxicity_score=3.5,
            bias_score=2.1,
            hallucination_score=4.8,
            explanations={
                'toxicity': 'Mild negative language detected',
                'bias': 'No significant bias indicators',
                'hallucination': 'Some unverified claims about features'
            }
        )
        
        assert result.toxicity_score == 3.5
        assert result.bias_score == 2.1
        assert result.hallucination_score == 4.8
        assert 'toxicity' in result.explanations
    
    def test_score_validation(self):
        """Test score validation (0-10 range)."""
        # Valid scores
        AnalysisResult(toxicity_score=0, bias_score=5, hallucination_score=10)
        
        # Invalid scores
        with pytest.raises(ValidationError):
            AnalysisResult(toxicity_score=-1, bias_score=5, hallucination_score=5)
        
        with pytest.raises(ValidationError):
            AnalysisResult(toxicity_score=11, bias_score=5, hallucination_score=5)
    
    def test_explanations_auto_fill(self):
        """Test that missing explanations are auto-filled."""
        result = AnalysisResult(
            toxicity_score=3.5,
            bias_score=2.1,
            hallucination_score=4.8,
            explanations={'toxicity': 'Some explanation'}
        )
        
        assert 'bias' in result.explanations
        assert 'hallucination' in result.explanations
        assert result.explanations['bias'] == "No explanation provided"


class TestModelMetadata:
    """Test ModelMetadata model."""
    
    def test_valid_metadata(self):
        """Test creating valid model metadata."""
        metadata = ModelMetadata(
            model_id='amazon.nova-premier-v1:0',
            prompt_version='1.0',
            inference_config={'temperature': 0.1, 'max_tokens': 1000},
            processing_time_ms=1500,
            cost_usd=0.005
        )
        
        assert metadata.model_id == 'amazon.nova-premier-v1:0'
        assert metadata.processing_time_ms == 1500
        assert metadata.cost_usd == 0.005


class TestPolicyDecision:
    """Test PolicyDecision model."""
    
    def test_approved_decision(self):
        """Test approved policy decision."""
        decision = PolicyDecision(
            approved=True,
            policy_version='1.0',
            decision_rationale='Content meets all policy requirements',
            evaluated_rules=['toxicity_rule', 'bias_rule']
        )
        
        assert decision.approved is True
        assert len(decision.policy_violations) == 0
        assert len(decision.evaluated_rules) == 2
    
    def test_rejected_decision(self):
        """Test rejected policy decision."""
        decision = PolicyDecision(
            approved=False,
            policy_violations=['high_toxicity', 'bias_detected'],
            policy_version='1.0',
            decision_rationale='Content violates toxicity and bias policies'
        )
        
        assert decision.approved is False
        assert len(decision.policy_violations) == 2


class TestReview:
    """Test Review model."""
    
    def test_valid_review(self):
        """Test creating a valid review."""
        review = Review(
            product_id='prod-123',
            user_id='user-456',
            content='Great product, highly recommend!',
            rating=5,
            region=Region.US_EAST_1,
            product_category=ProductCategory.ELECTRONICS
        )
        
        assert review.product_id == 'prod-123'
        assert review.rating == 5
        assert review.status == ReviewStatus.PENDING
        assert review.review_id is not None  # Auto-generated UUID
    
    def test_content_validation(self):
        """Test content validation."""
        # Valid content
        Review(
            product_id='prod-123',
            user_id='user-456',
            content='Valid review content',
            rating=5,
            region=Region.US_EAST_1,
            product_category=ProductCategory.ELECTRONICS
        )
        
        # Empty content should fail
        with pytest.raises(ValidationError):
            Review(
                product_id='prod-123',
                user_id='user-456',
                content='',
                rating=5,
                region=Region.US_EAST_1,
                product_category=ProductCategory.ELECTRONICS
            )
        
        # Whitespace-only content should fail
        with pytest.raises(ValidationError):
            Review(
                product_id='prod-123',
                user_id='user-456',
                content='   ',
                rating=5,
                region=Region.US_EAST_1,
                product_category=ProductCategory.ELECTRONICS
            )
    
    def test_rating_validation(self):
        """Test rating validation (1-5 range)."""
        # Valid ratings
        for rating in [1, 2, 3, 4, 5]:
            Review(
                product_id='prod-123',
                user_id='user-456',
                content='Test content',
                rating=rating,
                region=Region.US_EAST_1,
                product_category=ProductCategory.ELECTRONICS
            )
        
        # Invalid ratings
        for rating in [0, 6, -1]:
            with pytest.raises(ValidationError):
                Review(
                    product_id='prod-123',
                    user_id='user-456',
                    content='Test content',
                    rating=rating,
                    region=Region.US_EAST_1,
                    product_category=ProductCategory.ELECTRONICS
                )
    
    def test_dynamodb_serialization(self):
        """Test DynamoDB serialization and deserialization."""
        original_review = Review(
            product_id='prod-123',
            user_id='user-456',
            content='Great product!',
            rating=5,
            region=Region.US_EAST_1,
            product_category=ProductCategory.ELECTRONICS,
            analysis_result=AnalysisResult(
                toxicity_score=1.0,
                bias_score=0.5,
                hallucination_score=2.0,
                explanations={'toxicity': 'Low toxicity', 'bias': 'No bias', 'hallucination': 'Minor claims'}
            )
        )
        
        # Serialize to DynamoDB format
        item = original_review.to_dynamodb_item()
        assert 'review_id' in item
        assert 'analysis_result' in item
        
        # Deserialize back
        restored_review = Review.from_dynamodb_item(item)
        assert restored_review.product_id == original_review.product_id
        assert restored_review.analysis_result.toxicity_score == 1.0


class TestReviewSummary:
    """Test ReviewSummary model."""
    
    def test_valid_summary(self):
        """Test creating a valid review summary."""
        summary = ReviewSummary(
            product_id='prod-123',
            summary_text='Overall positive feedback with good build quality.',
            reviews_processed=10,
            reviews_excluded=2,
            exclusion_reasons=['high_toxicity', 'spam'],
            summary_quality_score=8.5
        )
        
        assert summary.product_id == 'prod-123'
        assert summary.reviews_processed == 10
        assert summary.reviews_excluded == 2
        assert len(summary.exclusion_reasons) == 2
    
    def test_review_count_validation(self):
        """Test review count validation."""
        # Valid counts
        ReviewSummary(
            product_id='prod-123',
            summary_text='Test summary',
            reviews_processed=5,
            reviews_excluded=0
        )
        
        # Negative counts should fail
        with pytest.raises(ValidationError):
            ReviewSummary(
                product_id='prod-123',
                summary_text='Test summary',
                reviews_processed=-1,
                reviews_excluded=0
            )
    
    def test_total_validation(self):
        """Test that at least one review must be processed or excluded."""
        # Valid: some reviews processed
        ReviewSummary(
            product_id='prod-123',
            summary_text='Test summary',
            reviews_processed=1,
            reviews_excluded=0
        )
        
        # Valid: some reviews excluded
        ReviewSummary(
            product_id='prod-123',
            summary_text='Test summary',
            reviews_processed=0,
            reviews_excluded=1
        )
        
        # Invalid: no reviews at all
        with pytest.raises(ValidationError):
            ReviewSummary(
                product_id='prod-123',
                summary_text='Test summary',
                reviews_processed=0,
                reviews_excluded=0
            )


class TestAuditEvent:
    """Test AuditEvent model."""
    
    def test_valid_audit_event(self):
        """Test creating a valid audit event."""
        event = AuditEvent(
            review_id='review-123',
            event_type=EventType.ANALYSIS,
            user_id='user-456',
            product_id='prod-789',
            region=Region.US_EAST_1,
            processing_duration_ms=1500
        )
        
        assert event.review_id == 'review-123'
        assert event.event_type == EventType.ANALYSIS
        assert event.processing_duration_ms == 1500
        assert event.ttl is not None  # Auto-generated TTL
    
    def test_opensearch_document_format(self):
        """Test OpenSearch document format."""
        event = AuditEvent(
            review_id='review-123',
            event_type=EventType.ANALYSIS,
            user_id='user-456',
            product_id='prod-789',
            region=Region.US_EAST_1,
            analysis_results=AnalysisResult(
                toxicity_score=3.0,
                bias_score=1.5,
                hallucination_score=4.2,
                explanations={'toxicity': 'test', 'bias': 'test', 'hallucination': 'test'}
            ),
            policy_decision=PolicyDecision(
                approved=True,
                policy_version='1.0'
            )
        )
        
        doc = event.to_opensearch_document()
        
        assert '@timestamp' in doc
        assert 'toxicity_score' in doc
        assert 'bias_score' in doc
        assert 'hallucination_score' in doc
        assert 'policy_approved' in doc
        assert doc['toxicity_score'] == 3.0
        assert doc['policy_approved'] is True
    
    def test_dynamodb_serialization(self):
        """Test DynamoDB serialization."""
        event = AuditEvent(
            review_id='review-123',
            event_type=EventType.POLICY_DECISION,
            user_id='user-456',
            product_id='prod-789',
            region=Region.EU_WEST_1,
            policy_decision=PolicyDecision(
                approved=False,
                policy_violations=['high_toxicity'],
                policy_version='1.0'
            )
        )
        
        item = event.to_dynamodb_item()
        
        assert item['event_type'] == 'POLICY_DECISION'
        assert item['region'] == 'eu-west-1'
        assert 'policy_decision' in item
        assert item['ttl'] is not None
        
        # Test deserialization
        restored_event = AuditEvent.from_dynamodb_item(item)
        assert restored_event.event_type == EventType.POLICY_DECISION
        assert restored_event.policy_decision.approved is False


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_json_serialization(self):
        """Test JSON serialization utilities."""
        review = Review(
            product_id='prod-123',
            user_id='user-456',
            content='Test content',
            rating=5,
            region=Region.US_EAST_1,
            product_category=ProductCategory.ELECTRONICS
        )
        
        # Serialize to JSON
        json_str = serialize_for_json(review)
        assert isinstance(json_str, str)
        
        # Deserialize back
        restored_review = deserialize_from_json(json_str, Review)
        assert restored_review.product_id == review.product_id
        assert restored_review.rating == review.rating


if __name__ == '__main__':
    pytest.main([__file__])