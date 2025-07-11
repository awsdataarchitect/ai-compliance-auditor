"""
Unit tests for Bedrock client.
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from botocore.exceptions import ClientError

from bedrock_client import (
    BedrockClient, BedrockResponse, BedrockError, BedrockThrottleError, 
    BedrockValidationError, retry_with_exponential_backoff
)
from models import ModelMetadata


class TestBedrockClient:
    """Test BedrockClient class."""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create a mock Bedrock client."""
        with patch('bedrock_client.boto3.client') as mock_boto_client:
            mock_client = Mock()
            mock_boto_client.return_value = mock_client
            
            # Mock successful response
            mock_response = {
                'body': Mock(),
                'ResponseMetadata': {'HTTPStatusCode': 200}
            }
            
            mock_response_body = {
                'output': {
                    'message': {
                        'content': [{'text': '{"toxicity_score": 2.5, "explanation": "Mild negative language"}'}]
                    }
                },
                'usage': {
                    'inputTokens': 100,
                    'outputTokens': 50
                }
            }
            
            mock_response['body'].read.return_value = json.dumps(mock_response_body).encode()
            mock_client.invoke_model.return_value = mock_response
            
            return BedrockClient()
    
    def test_initialization(self, mock_bedrock_client):
        """Test BedrockClient initialization."""
        client = mock_bedrock_client
        assert client.model_id is not None
        assert client.prompt_version is not None
        assert client.default_inference_config is not None
    
    def test_build_prompt_template(self, mock_bedrock_client):
        """Test prompt template building."""
        client = mock_bedrock_client
        
        # Test toxicity analysis template
        template = client._build_prompt_template('toxicity_analysis')
        assert 'toxicity' in template.lower()
        assert '{content}' in template
        
        # Test bias analysis template
        template = client._build_prompt_template('bias_analysis')
        assert 'bias' in template.lower()
        assert '{content}' in template
        
        # Test hallucination analysis template
        template = client._build_prompt_template('hallucination_analysis')
        assert 'hallucination' in template.lower()
        assert '{content}' in template
        
        # Test summarization template
        template = client._build_prompt_template('summarization')
        assert 'summary' in template.lower()
        assert '{reviews_content}' in template
    
    @pytest.mark.asyncio
    async def test_invoke_model_success(self, mock_bedrock_client):
        """Test successful model invocation."""
        client = mock_bedrock_client
        
        response = await client._invoke_model("Test prompt")
        
        assert isinstance(response, BedrockResponse)
        assert response.content is not None
        assert isinstance(response.model_metadata, ModelMetadata)
        assert response.processing_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_invoke_model_throttling_error(self, mock_bedrock_client):
        """Test throttling error handling."""
        client = mock_bedrock_client
        
        # Mock throttling error
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Request was throttled'
            }
        }
        client.client.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        with pytest.raises(BedrockThrottleError):
            await client._invoke_model("Test prompt")
    
    @pytest.mark.asyncio
    async def test_invoke_model_validation_error(self, mock_bedrock_client):
        """Test validation error handling."""
        client = mock_bedrock_client
        
        # Mock validation error
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid request'
            }
        }
        client.client.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        with pytest.raises(BedrockValidationError):
            await client._invoke_model("Test prompt")
    
    def test_parse_json_response_valid_json(self, mock_bedrock_client):
        """Test parsing valid JSON response."""
        client = mock_bedrock_client
        
        json_content = '{"toxicity_score": 3.5, "explanation": "Test explanation"}'
        result = client._parse_json_response(json_content)
        
        assert result['toxicity_score'] == 3.5
        assert result['explanation'] == "Test explanation"
    
    def test_parse_json_response_markdown_json(self, mock_bedrock_client):
        """Test parsing JSON wrapped in markdown."""
        client = mock_bedrock_client
        
        markdown_content = '''
        Here's the analysis:
        ```json
        {"toxicity_score": 4.0, "explanation": "Moderate toxicity"}
        ```
        '''
        result = client._parse_json_response(markdown_content)
        
        assert result['toxicity_score'] == 4.0
        assert result['explanation'] == "Moderate toxicity"
    
    def test_parse_json_response_invalid_json(self, mock_bedrock_client):
        """Test parsing invalid JSON response."""
        client = mock_bedrock_client
        
        invalid_content = "This is not JSON content"
        result = client._parse_json_response(invalid_content)
        
        assert 'error' in result
        assert 'raw_content' in result
        assert result['raw_content'] == invalid_content
    
    @pytest.mark.asyncio
    async def test_analyze_toxicity(self, mock_bedrock_client):
        """Test toxicity analysis."""
        client = mock_bedrock_client
        
        result = await client.analyze_toxicity("This is a test review")
        
        assert 'toxicity_score' in result
        assert 'model_metadata' in result
        client.client.invoke_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_bias(self, mock_bedrock_client):
        """Test bias analysis."""
        client = mock_bedrock_client
        
        result = await client.analyze_bias("This is a test review")
        
        assert 'model_metadata' in result
        client.client.invoke_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_hallucination(self, mock_bedrock_client):
        """Test hallucination analysis."""
        client = mock_bedrock_client
        
        result = await client.analyze_hallucination("This is a test review")
        
        assert 'model_metadata' in result
        client.client.invoke_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_summary(self, mock_bedrock_client):
        """Test summary generation."""
        client = mock_bedrock_client
        
        reviews_content = "Review 1: Great product. Review 2: Good quality."
        result = await client.generate_summary(reviews_content)
        
        assert 'model_metadata' in result
        client.client.invoke_model.assert_called_once()
        
        # Check that the call used increased token limit for summaries
        call_args = client.client.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        assert body['inferenceConfig']['maxTokens'] == 1500
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_bedrock_client):
        """Test health check when service is healthy."""
        client = mock_bedrock_client
        
        result = await client.health_check()
        
        assert result['status'] == 'healthy'
        assert 'model_id' in result
        assert 'response_time_ms' in result
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, mock_bedrock_client):
        """Test health check when service is unhealthy."""
        client = mock_bedrock_client
        client.client.invoke_model.side_effect = Exception("Service unavailable")
        
        result = await client.health_check()
        
        assert result['status'] == 'unhealthy'
        assert 'error' in result
    
    def test_get_model_info(self, mock_bedrock_client):
        """Test getting model information."""
        client = mock_bedrock_client
        
        info = client.get_model_info()
        
        assert 'model_id' in info
        assert 'prompt_version' in info
        assert 'max_retries' in info
        assert 'timeout_seconds' in info
        assert 'default_inference_config' in info


class TestRetryDecorator:
    """Test retry decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=3)
        async def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_throttling(self):
        """Test successful execution after throttling errors."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=3, base_delay=0.01)  # Fast retry for testing
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise BedrockThrottleError("Throttled")
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Test failure when max retry attempts are exceeded."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=2, base_delay=0.01)
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise BedrockThrottleError("Always throttled")
        
        with pytest.raises(BedrockThrottleError):
            await test_function()
        
        assert call_count == 3  # Initial attempt + 2 retries
    
    @pytest.mark.asyncio
    async def test_retry_non_throttling_error_no_retry(self):
        """Test that non-throttling errors are not retried."""
        call_count = 0
        
        @retry_with_exponential_backoff(max_retries=3)
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise BedrockValidationError("Validation error")
        
        with pytest.raises(BedrockValidationError):
            await test_function()
        
        assert call_count == 1  # No retries for validation errors


class TestBedrockResponse:
    """Test BedrockResponse dataclass."""
    
    def test_bedrock_response_creation(self):
        """Test creating a BedrockResponse."""
        metadata = ModelMetadata(
            model_id='test-model',
            prompt_version='1.0',
            inference_config={},
            processing_time_ms=1000
        )
        
        response = BedrockResponse(
            content='{"test": "response"}',
            model_metadata=metadata,
            raw_response={'output': 'test'},
            processing_time_ms=1000,
            cost_usd=0.005
        )
        
        assert response.content == '{"test": "response"}'
        assert response.model_metadata == metadata
        assert response.processing_time_ms == 1000
        assert response.cost_usd == 0.005


if __name__ == '__main__':
    pytest.main([__file__])