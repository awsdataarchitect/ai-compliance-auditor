"""
Configuration management for AI Compliance Auditor Lambda functions.
"""
import os
import boto3
from typing import Dict, Any, Optional
from functools import lru_cache

class Config:
    """Configuration manager for Lambda functions."""
    
    def __init__(self):
        self.ssm_client = boto3.client('ssm')
        self.parameter_prefix = '/ai-compliance'
    
    @lru_cache(maxsize=128)
    def get_parameter(self, parameter_name: str, default: Optional[str] = None) -> str:
        """Get parameter from SSM Parameter Store with caching."""
        try:
            full_parameter_name = f"{self.parameter_prefix}/{parameter_name}"
            response = self.ssm_client.get_parameter(
                Name=full_parameter_name,
                WithDecryption=True
            )
            return response['Parameter']['Value']
        except Exception as e:
            if default is not None:
                return default
            raise ValueError(f"Failed to get parameter {parameter_name}: {str(e)}")
    
    @lru_cache(maxsize=32)
    def get_parameters_by_path(self, path: str) -> Dict[str, str]:
        """Get multiple parameters by path prefix."""
        try:
            full_path = f"{self.parameter_prefix}/{path}"
            response = self.ssm_client.get_parameters_by_path(
                Path=full_path,
                Recursive=True,
                WithDecryption=True
            )
            
            parameters = {}
            for param in response['Parameters']:
                # Remove the prefix to get the relative parameter name
                key = param['Name'].replace(f"{full_path}/", "")
                parameters[key] = param['Value']
            
            return parameters
        except Exception as e:
            raise ValueError(f"Failed to get parameters by path {path}: {str(e)}")

# Global configuration instance
config = Config()

# Environment-based configuration
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AUDIT_TABLE_NAME = os.getenv('AUDIT_TABLE_NAME', 'ai-compliance-audit-logs')
REPORTS_BUCKET_NAME = os.getenv('REPORTS_BUCKET_NAME', '')
OPENSEARCH_ENDPOINT = os.getenv('OPENSEARCH_ENDPOINT', '')

# Default configuration values
DEFAULT_CONFIG = {
    'toxicity_threshold': '5.0',
    'bias_threshold': '3.0',
    'hallucination_threshold': '6.0',
    'bedrock_model_id': 'amazon.nova-premier-v1:0',
    'prompt_version': '1.0',
    'max_retries': '3',
    'timeout_seconds': '30',
}