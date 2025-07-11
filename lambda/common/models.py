"""
Data models for AI Compliance Auditor using Pydantic for validation.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
import uuid
import json


class ReviewStatus(str, Enum):
    """Review processing status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"


class EventType(str, Enum):
    """Audit event types."""
    ANALYSIS = "ANALYSIS"
    POLICY_DECISION = "POLICY_DECISION"
    SUMMARY_GENERATED = "SUMMARY_GENERATED"
    PII_DETECTION = "PII_DETECTION"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class ProductCategory(str, Enum):
    """Product categories for different moderation levels."""
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    TOYS = "toys"
    HEALTH = "health"
    FOOD = "food"
    OTHER = "other"


class Region(str, Enum):
    """Supported regions for compliance."""
    US_EAST_1 = "us-east-1"
    US_WEST_2 = "us-west-2"
    EU_WEST_1 = "eu-west-1"
    EU_CENTRAL_1 = "eu-central-1"
    AP_SOUTHEAST_1 = "ap-southeast-1"


class AnalysisResult(BaseModel):
    """Analysis results from Bedrock model."""
    toxicity_score: float = Field(..., ge=0, le=10, description="Toxicity score (0-10)")
    bias_score: float = Field(..., ge=0, le=10, description="Bias score (0-10)")
    hallucination_score: float = Field(..., ge=0, le=10, description="Hallucination score (0-10)")
    explanations: Dict[str, str] = Field(
        default_factory=dict,
        description="Explanations for each score"
    )
    confidence_scores: Optional[Dict[str, float]] = Field(
        default=None,
        description="Confidence scores for each analysis"
    )

    @validator('explanations')
    def validate_explanations(cls, v):
        """Ensure required explanation keys are present."""
        required_keys = ['toxicity', 'bias', 'hallucination']
        for key in required_keys:
            if key not in v:
                v[key] = "No explanation provided"
        return v


class ModelMetadata(BaseModel):
    """Metadata about the AI model used for analysis."""
    model_id: str = Field(..., description="Bedrock model identifier")
    prompt_version: str = Field(..., description="Version of the prompt template")
    inference_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Model inference configuration"
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Processing time in milliseconds"
    )
    cost_usd: Optional[float] = Field(
        default=None,
        description="Estimated cost in USD"
    )


class PolicyDecision(BaseModel):
    """Policy validation decision."""
    approved: bool = Field(..., description="Whether content was approved")
    policy_violations: List[str] = Field(
        default_factory=list,
        description="List of policy violations"
    )
    decision_rationale: str = Field(
        default="",
        description="Explanation for the decision"
    )
    policy_version: str = Field(..., description="Version of policies applied")
    evaluated_rules: List[str] = Field(
        default_factory=list,
        description="List of policy rules that were evaluated"
    )


class Review(BaseModel):
    """Product review model."""
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = Field(..., min_length=1, description="Product identifier")
    user_id: str = Field(..., min_length=1, description="User identifier")
    content: str = Field(..., min_length=1, max_length=5000, description="Review content")
    rating: int = Field(..., ge=1, le=5, description="Product rating (1-5)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    region: Region = Field(..., description="Region for compliance")
    product_category: ProductCategory = Field(..., description="Product category")
    
    # Analysis results
    analysis_result: Optional[AnalysisResult] = None
    policy_decision: Optional[PolicyDecision] = None
    
    # Processing status
    status: ReviewStatus = Field(default=ReviewStatus.PENDING)
    processing_errors: List[str] = Field(default_factory=list)
    
    # Metadata
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    language: Optional[str] = Field(default="en", description="Content language")

    @validator('content')
    def validate_content(cls, v):
        """Validate review content."""
        if not v.strip():
            raise ValueError("Review content cannot be empty")
        return v.strip()

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'review_id': self.review_id,
            'product_id': self.product_id,
            'user_id': self.user_id,
            'content': self.content,
            'rating': self.rating,
            'timestamp': self.timestamp.isoformat(),
            'region': self.region.value,
            'product_category': self.product_category.value,
            'status': self.status.value,
            'language': self.language or 'en'
        }
        
        if self.analysis_result:
            item['analysis_result'] = self.analysis_result.dict()
        
        if self.policy_decision:
            item['policy_decision'] = self.policy_decision.dict()
        
        if self.processing_errors:
            item['processing_errors'] = self.processing_errors
        
        if self.source_ip:
            item['source_ip'] = self.source_ip
        
        if self.user_agent:
            item['user_agent'] = self.user_agent
        
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'Review':
        """Create Review from DynamoDB item."""
        # Convert timestamp string back to datetime
        timestamp = datetime.fromisoformat(item['timestamp'])
        
        # Create the review object
        review_data = {
            'review_id': item['review_id'],
            'product_id': item['product_id'],
            'user_id': item['user_id'],
            'content': item['content'],
            'rating': item['rating'],
            'timestamp': timestamp,
            'region': Region(item['region']),
            'product_category': ProductCategory(item['product_category']),
            'status': ReviewStatus(item['status']),
            'language': item.get('language', 'en')
        }
        
        # Add optional fields
        if 'analysis_result' in item:
            review_data['analysis_result'] = AnalysisResult(**item['analysis_result'])
        
        if 'policy_decision' in item:
            review_data['policy_decision'] = PolicyDecision(**item['policy_decision'])
        
        if 'processing_errors' in item:
            review_data['processing_errors'] = item['processing_errors']
        
        if 'source_ip' in item:
            review_data['source_ip'] = item['source_ip']
        
        if 'user_agent' in item:
            review_data['user_agent'] = item['user_agent']
        
        return cls(**review_data)


class ReviewSummary(BaseModel):
    """Summary of multiple product reviews."""
    summary_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = Field(..., min_length=1, description="Product identifier")
    summary_text: str = Field(..., min_length=1, description="Generated summary")
    reviews_processed: int = Field(..., ge=0, description="Number of reviews processed")
    reviews_excluded: int = Field(..., ge=0, description="Number of reviews excluded")
    exclusion_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for excluding reviews"
    )
    
    # Quality metrics
    summary_quality_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=10,
        description="Quality score of the summary"
    )
    factual_accuracy_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=10,
        description="Factual accuracy score"
    )
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_metadata: Optional[ModelMetadata] = None
    policy_constraints: Dict[str, float] = Field(
        default_factory=dict,
        description="Policy constraints applied during summarization"
    )

    @validator('reviews_processed', 'reviews_excluded')
    def validate_review_counts(cls, v):
        """Validate review counts are non-negative."""
        if v < 0:
            raise ValueError("Review counts must be non-negative")
        return v

    @root_validator(skip_on_failure=True)
    def validate_review_totals(cls, values):
        """Validate that processed + excluded makes sense."""
        processed = values.get('reviews_processed', 0)
        excluded = values.get('reviews_excluded', 0)
        
        if processed == 0 and excluded == 0:
            raise ValueError("At least one review must be processed or excluded")
        
        return values

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'summary_id': self.summary_id,
            'product_id': self.product_id,
            'summary_text': self.summary_text,
            'reviews_processed': self.reviews_processed,
            'reviews_excluded': self.reviews_excluded,
            'exclusion_reasons': self.exclusion_reasons,
            'generated_at': self.generated_at.isoformat(),
            'policy_constraints': self.policy_constraints
        }
        
        if self.summary_quality_score is not None:
            item['summary_quality_score'] = self.summary_quality_score
        
        if self.factual_accuracy_score is not None:
            item['factual_accuracy_score'] = self.factual_accuracy_score
        
        if self.model_metadata:
            item['model_metadata'] = self.model_metadata.dict()
        
        return item


class AuditEvent(BaseModel):
    """Audit event for compliance logging."""
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    review_id: str = Field(..., min_length=1, description="Associated review ID")
    event_type: EventType = Field(..., description="Type of audit event")
    user_id: str = Field(..., min_length=1, description="User identifier")
    product_id: str = Field(..., min_length=1, description="Product identifier")
    region: Region = Field(..., description="Processing region")
    
    # Model metadata
    model_metadata: Optional[ModelMetadata] = None
    
    # Event-specific data
    analysis_results: Optional[AnalysisResult] = None
    policy_decision: Optional[PolicyDecision] = None
    summary_data: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # Performance metrics
    processing_duration_ms: int = Field(default=0, ge=0)
    memory_used_mb: Optional[int] = None
    
    # TTL for data retention (Unix timestamp)
    ttl: Optional[int] = None

    def __init__(self, **data):
        super().__init__(**data)
        # Set TTL to 7 years from now (for compliance retention)
        if self.ttl is None:
            retention_years = 7
            retention_seconds = retention_years * 365 * 24 * 60 * 60
            self.ttl = int(self.timestamp.timestamp()) + retention_seconds

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'audit_id': self.audit_id,
            'timestamp': self.timestamp.isoformat(),
            'review_id': self.review_id,
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'region': self.region.value,
            'processing_duration_ms': self.processing_duration_ms,
            'ttl': self.ttl
        }
        
        if self.model_metadata:
            item['model_metadata'] = self.model_metadata.dict()
        
        if self.analysis_results:
            item['analysis_results'] = self.analysis_results.dict()
        
        if self.policy_decision:
            item['policy_decision'] = self.policy_decision.dict()
        
        if self.summary_data:
            item['summary_data'] = self.summary_data
        
        if self.error_details:
            item['error_details'] = self.error_details
        
        if self.memory_used_mb:
            item['memory_used_mb'] = self.memory_used_mb
        
        return item

    def to_opensearch_document(self) -> Dict[str, Any]:
        """Convert to OpenSearch document format."""
        doc = {
            '@timestamp': self.timestamp.isoformat(),
            'audit_id': self.audit_id,
            'review_id': self.review_id,
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'region': self.region.value,
            'processing_duration_ms': self.processing_duration_ms
        }
        
        # Add analysis scores for easy querying
        if self.analysis_results:
            doc.update({
                'toxicity_score': self.analysis_results.toxicity_score,
                'bias_score': self.analysis_results.bias_score,
                'hallucination_score': self.analysis_results.hallucination_score
            })
        
        # Add policy decision info
        if self.policy_decision:
            doc.update({
                'policy_approved': self.policy_decision.approved,
                'policy_violations_count': len(self.policy_decision.policy_violations),
                'policy_version': self.policy_decision.policy_version
            })
        
        # Add model info
        if self.model_metadata:
            doc.update({
                'model_id': self.model_metadata.model_id,
                'prompt_version': self.model_metadata.prompt_version
            })
            if self.model_metadata.cost_usd:
                doc['cost_usd'] = self.model_metadata.cost_usd
        
        if self.memory_used_mb:
            doc['memory_used_mb'] = self.memory_used_mb
        
        return doc

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'AuditEvent':
        """Create AuditEvent from DynamoDB item."""
        # Convert timestamp string back to datetime
        timestamp = datetime.fromisoformat(item['timestamp'])
        
        # Create the audit event object
        event_data = {
            'audit_id': item['audit_id'],
            'timestamp': timestamp,
            'review_id': item['review_id'],
            'event_type': EventType(item['event_type']),
            'user_id': item['user_id'],
            'product_id': item['product_id'],
            'region': Region(item['region']),
            'processing_duration_ms': item.get('processing_duration_ms', 0),
            'ttl': item.get('ttl')
        }
        
        # Add optional fields
        if 'model_metadata' in item:
            event_data['model_metadata'] = ModelMetadata(**item['model_metadata'])
        
        if 'analysis_results' in item:
            event_data['analysis_results'] = AnalysisResult(**item['analysis_results'])
        
        if 'policy_decision' in item:
            event_data['policy_decision'] = PolicyDecision(**item['policy_decision'])
        
        if 'summary_data' in item:
            event_data['summary_data'] = item['summary_data']
        
        if 'error_details' in item:
            event_data['error_details'] = item['error_details']
        
        if 'memory_used_mb' in item:
            event_data['memory_used_mb'] = item['memory_used_mb']
        
        return cls(**event_data)


# Utility functions for model serialization
def serialize_for_json(obj: Union[BaseModel, List[BaseModel], Dict]) -> str:
    """Serialize Pydantic models to JSON string."""
    if isinstance(obj, BaseModel):
        return obj.json()
    elif isinstance(obj, list):
        return json.dumps([item.dict() if isinstance(item, BaseModel) else item for item in obj])
    elif isinstance(obj, dict):
        return json.dumps(obj)
    else:
        return json.dumps(obj)


def deserialize_from_json(json_str: str, model_class: type) -> BaseModel:
    """Deserialize JSON string to Pydantic model."""
    data = json.loads(json_str)
    return model_class(**data)