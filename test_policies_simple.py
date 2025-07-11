#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda'))

from common.policies import PolicyEngine, PolicyContext, PolicyDecision

def test_policy_engine():
    """Simple test for policy engine functionality"""
    
    # Test basic functionality
    engine = PolicyEngine()
    context = PolicyContext(
        region='us-east-1', 
        product_category='electronics', 
        compliance_mode='standard'
    )
    
    # Test approval case
    analysis_result = {
        'toxicity_score': 2.0, 
        'bias_score': 1.0, 
        'hallucination_score': 3.0
    }
    result = engine.evaluate_content_policy(analysis_result, context)
    print(f'✅ Approval test: {result.decision.value} - {result.explanation}')
    assert result.decision == PolicyDecision.ALLOW
    
    # Test violation case
    analysis_result = {
        'toxicity_score': 8.0, 
        'bias_score': 1.0, 
        'hallucination_score': 3.0
    }
    result = engine.evaluate_content_policy(analysis_result, context)
    print(f'✅ Violation test: {result.decision.value} - {result.explanation}')
    assert result.decision == PolicyDecision.DENY
    
    # Test regional compliance
    eu_context = PolicyContext(
        region='eu-west-1', 
        product_category='electronics', 
        compliance_mode='standard'
    )
    analysis_result = {
        'toxicity_score': 4.0,  # Above EU limit of 3.0
        'bias_score': 1.0, 
        'hallucination_score': 3.0
    }
    result = engine.evaluate_content_policy(analysis_result, eu_context)
    print(f'✅ Regional compliance test: {result.decision.value} - {result.explanation}')
    assert result.decision == PolicyDecision.DENY
    
    # Test category restrictions
    children_context = PolicyContext(
        region='us-east-1', 
        product_category='children_toys', 
        compliance_mode='standard'
    )
    analysis_result = {
        'toxicity_score': 2.0,  # Above children_toys limit of 1.0
        'bias_score': 0.5, 
        'hallucination_score': 1.0
    }
    result = engine.evaluate_content_policy(analysis_result, children_context)
    print(f'✅ Category restriction test: {result.decision.value} - {result.explanation}')
    assert result.decision == PolicyDecision.DENY
    
    # Test summary policy
    summary_data = {
        'reviews_excluded': 2,
        'total_reviews': 10,
        'quality_score': 8.0
    }
    result = engine.evaluate_summary_policy(summary_data, context)
    print(f'✅ Summary approval test: {result.decision.value} - {result.explanation}')
    assert result.decision == PolicyDecision.ALLOW
    
    print('\n🎉 All policy engine tests passed!')

if __name__ == '__main__':
    test_policy_engine()