"""
Unit tests for policy engine
"""

import pytest
from lambda.common.policies import (
    PolicyEngine, PolicyContext, PolicyDecision, PolicyReason,
    evaluate_content_policy, evaluate_summary_policy
)

class TestPolicyEngine:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.policy_engine = PolicyEngine()
        self.context = PolicyContext(
            region="us-east-1",
            product_category="electronics",
            compliance_mode="standard"
        )
    
    def test_content_policy_approval(self):
        """Test content that should be approved"""
        analysis_result = {
            "toxicity_score": 2.0,
            "bias_score": 1.0,
            "hallucination_score": 3.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, self.context)
        
        assert result.decision == PolicyDecision.ALLOW
        assert PolicyReason.APPROVED in result.reasons
        assert "meets all policy requirements" in result.explanation
    
    def test_content_policy_toxicity_violation(self):
        """Test content with high toxicity score"""
        analysis_result = {
            "toxicity_score": 8.0,  # Above standard threshold of 5.0
            "bias_score": 1.0,
            "hallucination_score": 3.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, self.context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.TOXICITY_THRESHOLD in result.reasons
        assert "Toxicity score 8.0 exceeds threshold 5.0" in result.explanation
    
    def test_content_policy_bias_violation(self):
        """Test content with high bias score"""
        analysis_result = {
            "toxicity_score": 2.0,
            "bias_score": 6.0,  # Above standard threshold of 4.0
            "hallucination_score": 3.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, self.context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.BIAS_THRESHOLD in result.reasons
        assert "Bias score 6.0 exceeds threshold 4.0" in result.explanation
    
    def test_content_policy_hallucination_violation(self):
        """Test content with high hallucination score"""
        analysis_result = {
            "toxicity_score": 2.0,
            "bias_score": 1.0,
            "hallucination_score": 8.0  # Above standard threshold of 6.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, self.context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.HALLUCINATION_THRESHOLD in result.reasons
        assert "Hallucination score 8.0 exceeds threshold 6.0" in result.explanation
    
    def test_content_policy_multiple_violations(self):
        """Test content with multiple policy violations"""
        analysis_result = {
            "toxicity_score": 8.0,
            "bias_score": 6.0,
            "hallucination_score": 8.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, self.context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.TOXICITY_THRESHOLD in result.reasons
        assert PolicyReason.BIAS_THRESHOLD in result.reasons
        assert PolicyReason.HALLUCINATION_THRESHOLD in result.reasons
    
    def test_content_policy_regional_compliance(self):
        """Test regional compliance policies"""
        eu_context = PolicyContext(
            region="eu-west-1",
            product_category="electronics",
            compliance_mode="standard"
        )
        
        analysis_result = {
            "toxicity_score": 4.0,  # Above EU limit of 3.0
            "bias_score": 1.0,
            "hallucination_score": 3.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, eu_context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.REGIONAL_COMPLIANCE in result.reasons
        assert "Regional toxicity limit exceeded for eu-west-1" in result.explanation
    
    def test_content_policy_category_restrictions(self):
        """Test product category restrictions"""
        children_context = PolicyContext(
            region="us-east-1",
            product_category="children_toys",
            compliance_mode="standard"
        )
        
        analysis_result = {
            "toxicity_score": 2.0,  # Above children_toys limit of 1.0
            "bias_score": 0.5,
            "hallucination_score": 1.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, children_context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.CATEGORY_RESTRICTION in result.reasons
        assert "Category toxicity limit exceeded for children_toys" in result.explanation
    
    def test_content_policy_strict_mode(self):
        """Test strict compliance mode"""
        strict_context = PolicyContext(
            region="us-east-1",
            product_category="electronics",
            compliance_mode="strict"
        )
        
        analysis_result = {
            "toxicity_score": 4.0,  # Above strict threshold of 3.0
            "bias_score": 1.0,
            "hallucination_score": 3.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, strict_context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.TOXICITY_THRESHOLD in result.reasons
    
    def test_content_policy_mild_mode(self):
        """Test mild compliance mode"""
        mild_context = PolicyContext(
            region="us-east-1",
            product_category="electronics",
            compliance_mode="mild"
        )
        
        analysis_result = {
            "toxicity_score": 6.0,  # Below mild threshold of 8.0
            "bias_score": 5.0,      # Below mild threshold of 7.0
            "hallucination_score": 7.0  # Below mild threshold of 8.0
        }
        
        result = self.policy_engine.evaluate_content_policy(analysis_result, mild_context)
        
        assert result.decision == PolicyDecision.ALLOW
        assert PolicyReason.APPROVED in result.reasons
    
    def test_summary_policy_approval(self):
        """Test summary that should be approved"""
        summary_data = {
            "reviews_excluded": 2,
            "total_reviews": 10,
            "quality_score": 8.0
        }
        
        result = self.policy_engine.evaluate_summary_policy(summary_data, self.context)
        
        assert result.decision == PolicyDecision.ALLOW
        assert PolicyReason.APPROVED in result.reasons
    
    def test_summary_policy_high_exclusion_rate(self):
        """Test summary with high exclusion rate"""
        summary_data = {
            "reviews_excluded": 8,  # 80% exclusion rate
            "total_reviews": 10,
            "quality_score": 8.0
        }
        
        result = self.policy_engine.evaluate_summary_policy(summary_data, self.context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.REGIONAL_COMPLIANCE in result.reasons
        assert "High exclusion rate: 80.00%" in result.explanation
    
    def test_summary_policy_low_quality(self):
        """Test summary with low quality score"""
        summary_data = {
            "reviews_excluded": 2,
            "total_reviews": 10,
            "quality_score": 3.0  # Below threshold of 5.0
        }
        
        result = self.policy_engine.evaluate_summary_policy(summary_data, self.context)
        
        assert result.decision == PolicyDecision.DENY
        assert PolicyReason.HALLUCINATION_THRESHOLD in result.reasons
        assert "Summary quality score 3.0 below threshold" in result.explanation
    
    def test_policy_threshold_updates(self):
        """Test dynamic policy threshold updates"""
        original_toxicity = self.policy_engine.policies["toxicity"]["standard"]
        
        updates = {
            "toxicity": {
                "standard": 7.0
            }
        }
        
        self.policy_engine.update_policy_thresholds(updates)
        
        assert self.policy_engine.policies["toxicity"]["standard"] == 7.0
        assert self.policy_engine.policies["toxicity"]["standard"] != original_toxicity
    
    def test_policy_summary(self):
        """Test policy summary generation"""
        summary = self.policy_engine.get_policy_summary()
        
        assert "policy_version" in summary
        assert "policies" in summary
        assert "toxicity" in summary["policies"]
        assert "bias" in summary["policies"]
        assert "hallucination" in summary["policies"]
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        analysis_result = {
            "toxicity_score": 2.0,
            "bias_score": 1.0,
            "hallucination_score": 3.0
        }
        
        # Test content policy convenience function
        result = evaluate_content_policy(analysis_result, self.context)
        assert result.decision == PolicyDecision.ALLOW
        
        # Test summary policy convenience function
        summary_data = {
            "reviews_excluded": 2,
            "total_reviews": 10,
            "quality_score": 8.0
        }
        
        result = evaluate_summary_policy(summary_data, self.context)
        assert result.decision == PolicyDecision.ALLOW

if __name__ == "__main__":
    pytest.main([__file__])