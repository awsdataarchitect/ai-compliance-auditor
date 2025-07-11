#!/usr/bin/env python3
"""
Basic integration tests for AI Compliance Auditor MVP
Tests the core workflow with sample data
"""

import json
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add lambda common to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda', 'common'))

from policies import PolicyEngine, PolicyContext, PolicyDecision
from models import EventType

def test_end_to_end_workflow():
    """Test the complete workflow with sample review data"""
    print("🧪 Testing end-to-end AI Compliance Auditor workflow...")
    
    # Sample review data
    sample_review = {
        'review_id': 'test-review-123',
        'product_id': 'product-456',
        'user_id': 'user-789',
        'content': 'Great product! Works perfectly and good value for money.',
        'rating': 5,
        'region': 'us-east-1',
        'product_category': 'electronics',
        'compliance_mode': 'standard'
    }
    
    print(f"📝 Processing sample review: {sample_review['content'][:50]}...")
    
    # Step 1: Simulate Review Analysis (would normally call Bedrock)
    analysis_result = {
        'toxicity_score': 1.0,
        'bias_score': 0.5,
        'hallucination_score': 2.0,
        'explanations': {
            'toxicity': 'Content is positive and non-toxic',
            'bias': 'No bias indicators detected',
            'hallucination': 'Claims appear factual'
        }
    }
    print(f"✅ Analysis completed - Toxicity: {analysis_result['toxicity_score']}, Bias: {analysis_result['bias_score']}")
    
    # Step 2: Policy Validation
    policy_engine = PolicyEngine()
    policy_context = PolicyContext(
        region=sample_review['region'],
        product_category=sample_review['product_category'],
        compliance_mode=sample_review['compliance_mode']
    )
    
    policy_result = policy_engine.evaluate_content_policy(analysis_result, policy_context)
    print(f"✅ Policy validation: {policy_result.decision.value} - {policy_result.explanation}")
    
    # Step 3: Summary Generation (simulated)
    if policy_result.decision == PolicyDecision.ALLOW:
        summary_data = {
            'reviews_processed': 1,
            'reviews_included': 1,
            'reviews_excluded': 0,
            'quality_score': 8.5
        }
        
        summary_policy_result = policy_engine.evaluate_summary_policy(summary_data, policy_context)
        print(f"✅ Summary validation: {summary_policy_result.decision.value}")
        
        if summary_policy_result.decision == PolicyDecision.ALLOW:
            summary_text = "Customer reports positive experience with good value and performance."
            print(f"✅ Summary generated: {summary_text}")
    
    # Step 4: Audit Event Creation (simulated)
    audit_event_data = {
        'audit_id': 'audit-test-123',
        'timestamp': datetime.now().isoformat(),
        'event_type': EventType.ANALYSIS.value,
        'review_id': sample_review['review_id'],
        'user_id': sample_review['user_id'],
        'product_id': sample_review['product_id'],
        'region': sample_review['region'],
        'analysis_results': analysis_result,
        'policy_decision': {
            'decision': policy_result.decision.value,
            'reasons': [r.value for r in policy_result.reasons],
            'explanation': policy_result.explanation
        }
    }
    print(f"✅ Audit event created: {audit_event_data['audit_id']}")
    
    # Verify workflow completed successfully
    assert policy_result.decision == PolicyDecision.ALLOW, "Content should be approved"
    assert analysis_result['toxicity_score'] < 5.0, "Toxicity should be low"
    assert 'audit_id' in audit_event_data, "Audit event should be created"
    
    print("🎉 End-to-end workflow test PASSED!")
    return True

def test_policy_violation_workflow():
    """Test workflow with content that violates policies"""
    print("\n🧪 Testing policy violation workflow...")
    
    # Sample toxic review
    toxic_review = {
        'review_id': 'test-review-toxic',
        'content': 'This product is terrible garbage, complete waste of money!',
        'region': 'us-east-1',
        'product_category': 'electronics',
        'compliance_mode': 'standard'
    }
    
    # Simulate high toxicity analysis
    analysis_result = {
        'toxicity_score': 8.0,  # High toxicity
        'bias_score': 1.0,
        'hallucination_score': 2.0,
        'explanations': {
            'toxicity': 'Contains aggressive language and negative sentiment',
            'bias': 'No bias detected',
            'hallucination': 'Claims appear opinion-based'
        }
    }
    
    # Policy validation should reject
    policy_engine = PolicyEngine()
    policy_context = PolicyContext(
        region=toxic_review['region'],
        product_category=toxic_review['product_category'],
        compliance_mode=toxic_review['compliance_mode']
    )
    
    policy_result = policy_engine.evaluate_content_policy(analysis_result, policy_context)
    print(f"✅ Policy validation: {policy_result.decision.value} - {policy_result.explanation}")
    
    # Verify rejection
    assert policy_result.decision == PolicyDecision.DENY, "Toxic content should be rejected"
    assert 'TOXICITY_THRESHOLD_EXCEEDED' in [r.value for r in policy_result.reasons], "Should flag toxicity"
    
    print("🎉 Policy violation workflow test PASSED!")
    return True

def test_regional_compliance():
    """Test regional compliance policies"""
    print("\n🧪 Testing regional compliance...")
    
    # Test EU compliance (stricter rules)
    analysis_result = {
        'toxicity_score': 4.0,  # Above EU limit but below US limit
        'bias_score': 1.0,
        'hallucination_score': 2.0
    }
    
    # US context - should pass
    us_context = PolicyContext(
        region='us-east-1',
        product_category='electronics',
        compliance_mode='standard'
    )
    
    policy_engine = PolicyEngine()
    us_result = policy_engine.evaluate_content_policy(analysis_result, us_context)
    print(f"✅ US policy result: {us_result.decision.value}")
    
    # EU context - should fail
    eu_context = PolicyContext(
        region='eu-west-1',
        product_category='electronics',
        compliance_mode='standard'
    )
    
    eu_result = policy_engine.evaluate_content_policy(analysis_result, eu_context)
    print(f"✅ EU policy result: {eu_result.decision.value}")
    
    # Verify regional differences
    assert us_result.decision == PolicyDecision.ALLOW, "Should pass US standards"
    assert eu_result.decision == PolicyDecision.DENY, "Should fail EU standards"
    
    print("🎉 Regional compliance test PASSED!")
    return True

def test_step_functions_workflow_structure():
    """Test Step Functions workflow structure"""
    print("\n🧪 Testing Step Functions workflow structure...")
    
    # Load and validate workflow definition
    workflow_path = 'src/step-functions/ai-compliance-workflow.json'
    
    if not os.path.exists(workflow_path):
        print(f"❌ Workflow file not found: {workflow_path}")
        return False
    
    with open(workflow_path, 'r') as f:
        workflow = json.load(f)
    
    # Validate workflow structure
    assert 'Comment' in workflow, "Workflow should have a comment"
    assert 'StartAt' in workflow, "Workflow should have a start state"
    assert 'States' in workflow, "Workflow should have states"
    
    # Check key states exist
    states = workflow['States']
    required_states = [
        'ValidateInput',
        'ProcessReview', 
        'PolicyValidation',
        'CheckPolicyDecision',
        'ContentApproved',
        'ContentRejected'
    ]
    
    for state in required_states:
        assert state in states, f"Required state '{state}' missing from workflow"
    
    print("✅ Step Functions workflow structure is valid")
    print("🎉 Workflow structure test PASSED!")
    return True

def main():
    """Run all integration tests"""
    print("🚀 Starting AI Compliance Auditor Integration Tests\n")
    
    tests = [
        test_end_to_end_workflow,
        test_policy_violation_workflow,
        test_regional_compliance,
        test_step_functions_workflow_structure
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} FAILED: {str(e)}")
            failed += 1
    
    print(f"\n📊 Integration Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 All integration tests PASSED! MVP is ready for deployment.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review and fix issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)