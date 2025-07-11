"""
Unit tests for Policy Validator Lambda handler
"""

import json
from unittest.mock import Mock
import sys
import os

# Add the common layer to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from handler import lambda_handler, validate_content, validate_summary, update_policy_configuration, get_policy_configuration
from policies import PolicyContext, PolicyDecision

class TestPolicyValidatorHandler:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'test-request-123'
        self.mock_context.function_name = 'policy-validator-test'
    
    def test_content_validation_approval(self):
        """Test content validation that should be approved"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 2.0,
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'ALLOW'
        assert 'meets all policy requirements' in result['validation_result']['explanation']
    
    def test_content_validation_denial(self):
        """Test content validation that should be denied"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 8.0,  # Above threshold
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'DENY'
        assert 'TOXICITY_THRESHOLD_EXCEEDED' in result['validation_result']['reasons']
    
    def test_summary_validation_approval(self):
        """Test summary validation that should be approved"""
        event = {
            'validation_type': 'summary',
            'analysis_result': {
                'reviews_excluded': 2,
                'total_reviews': 10,
                'quality_score': 8.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'ALLOW'
    
    def test_summary_validation_high_exclusion_rate(self):
        """Test summary validation with high exclusion rate"""
        event = {
            'validation_type': 'summary',
            'analysis_result': {
                'reviews_excluded': 8,  # 80% exclusion rate
                'total_reviews': 10,
                'quality_score': 8.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'DENY'
        assert 'High exclusion rate' in result['validation_result']['explanation']
    
    def test_regional_compliance_eu(self):
        """Test EU regional compliance"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 4.0,  # Above EU limit
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            'policy_context': {
                'region': 'eu-west-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'DENY'
        assert 'REGIONAL_COMPLIANCE_VIOLATION' in result['validation_result']['reasons']
    
    def test_category_restrictions_children_toys(self):
        """Test children toys category restrictions"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 2.0,  # Above children_toys limit
                'bias_score': 0.5,
                'hallucination_score': 1.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'children_toys',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'DENY'
        assert 'CATEGORY_RESTRICTION_VIOLATION' in result['validation_result']['reasons']
    
    def test_compliance_mode_strict(self):
        """Test strict compliance mode"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 4.0,  # Above strict threshold
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'strict'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'DENY'
        assert 'TOXICITY_THRESHOLD_EXCEEDED' in result['validation_result']['reasons']
    
    def test_compliance_mode_mild(self):
        """Test mild compliance mode"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 6.0,  # Below mild threshold
                'bias_score': 5.0,
                'hallucination_score': 7.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'mild'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'ALLOW'
    
    def test_missing_validation_type(self):
        """Test handling of missing validation type (defaults to content)"""
        event = {
            'analysis_result': {
                'toxicity_score': 2.0,
                'bias_score': 1.0,
                'hallucination_score': 3.0
            },
            'policy_context': {
                'region': 'us-east-1',
                'product_category': 'electronics',
                'compliance_mode': 'standard'
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['validation_result']['decision'] == 'ALLOW'
    
    def test_invalid_validation_type(self):
        """Test handling of invalid validation type"""
        event = {
            'validation_type': 'invalid_type',
            'analysis_result': {},
            'policy_context': {}
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 500
        assert result['error']['type'] == 'PolicyValidationError'
        assert 'Unknown validation type' in result['error']['message']
    
    def test_missing_policy_context(self):
        """Test handling of missing policy context (uses defaults)"""
        event = {
            'validation_type': 'content',
            'analysis_result': {
                'toxicity_score': 2.0,
                'bias_score': 1.0,
                'hallucination_score': 3.0
            }
        }
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert result['policy_context']['region'] == 'us-east-1'
        assert result['policy_context']['product_category'] == 'general'
        assert result['policy_context']['compliance_mode'] == 'standard'
    
    def test_update_policy_configuration(self):
        """Test policy configuration update"""
        event = {
            'policy_updates': {
                'toxicity': {
                    'standard': 7.0
                }
            }
        }
        
        result = update_policy_configuration(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert 'Policy configuration updated successfully' in result['message']
        assert result['updated_policies'] == event['policy_updates']
    
    def test_get_policy_configuration(self):
        """Test policy configuration retrieval"""
        event = {}
        
        result = get_policy_configuration(event, self.mock_context)
        
        assert result['statusCode'] == 200
        assert 'policy_configuration' in result
        assert 'policy_version' in result['policy_configuration']
        assert 'policies' in result['policy_configuration']
    
    def test_error_handling(self):
        """Test error handling for malformed events"""
        event = None  # This should cause an error
        
        result = lambda_handler(event, self.mock_context)
        
        assert result['statusCode'] == 500
        assert result['error']['type'] == 'PolicyValidationError'
        assert result['validation_result']['decision'] == 'DENY'

if __name__ == "__main__":
    # Run a simple test
    test_instance = TestPolicyValidatorHandler()
    test_instance.setup_method()
    
    print("Running Policy Validator Lambda tests...")
    
    # Test content validation approval
    test_instance.test_content_validation_approval()
    print("✅ Content validation approval test passed")
    
    # Test content validation denial
    test_instance.test_content_validation_denial()
    print("✅ Content validation denial test passed")
    
    # Test summary validation
    test_instance.test_summary_validation_approval()
    print("✅ Summary validation test passed")
    
    # Test regional compliance
    test_instance.test_regional_compliance_eu()
    print("✅ Regional compliance test passed")
    
    # Test category restrictions
    test_instance.test_category_restrictions_children_toys()
    print("✅ Category restrictions test passed")
    
    # Test configuration functions
    test_instance.test_get_policy_configuration()
    print("✅ Policy configuration retrieval test passed")
    
    print("\n🎉 All Policy Validator Lambda tests passed!")