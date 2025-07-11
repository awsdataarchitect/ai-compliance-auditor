"""
Policy definitions and validation logic for AI Compliance Auditor MVP.
This is a simplified policy engine that can be upgraded to Cedar/AWS Verified Permissions later.

This module provides:
- Policy evaluation for content moderation
- Regional compliance checking
- Category-specific restrictions
- Configurable thresholds for different compliance modes
"""

from typing import Dict, List, Any, Optional, Union, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class PolicyDecision(Enum):
    """Policy evaluation decisions."""
    ALLOW = "ALLOW"
    DENY = "DENY"

class PolicyReason(Enum):
    """Reasons for policy decisions."""
    TOXICITY_THRESHOLD = "TOXICITY_THRESHOLD_EXCEEDED"
    BIAS_THRESHOLD = "BIAS_THRESHOLD_EXCEEDED"
    HALLUCINATION_THRESHOLD = "HALLUCINATION_THRESHOLD_EXCEEDED"
    REGIONAL_COMPLIANCE = "REGIONAL_COMPLIANCE_VIOLATION"
    CATEGORY_RESTRICTION = "CATEGORY_RESTRICTION_VIOLATION"
    APPROVED = "CONTENT_APPROVED"

class ComplianceMode(Enum):
    """Compliance strictness levels."""
    MILD = "mild"
    STANDARD = "standard"
    STRICT = "strict"

class ScoreThresholds(NamedTuple):
    """Score thresholds for different analysis types."""
    toxicity: float
    bias: float
    hallucination: float

@dataclass
class PolicyContext:
    """Context information for policy evaluation"""
    region: str
    product_category: str
    user_tier: str = "standard"  # standard, premium, enterprise
    compliance_mode: str = "standard"  # mild, standard, strict

@dataclass
class PolicyResult:
    """Result of policy evaluation"""
    decision: PolicyDecision
    reasons: List[PolicyReason]
    explanation: str
    metadata: Dict[str, Any]

class PolicyEngine:
    """Simplified policy engine for MVP - can be replaced with Cedar later"""
    
    def __init__(self):
        self.policies = self._load_default_policies()
    
    def _load_default_policies(self) -> Dict[str, Dict[str, Any]]:
        """Load default policy thresholds"""
        return {
            "toxicity": {
                "mild": 8.0,
                "standard": 5.0,
                "strict": 3.0
            },
            "bias": {
                "mild": 7.0,
                "standard": 4.0,
                "strict": 2.0
            },
            "hallucination": {
                "mild": 8.0,
                "standard": 6.0,
                "strict": 4.0
            },
            "regional_compliance": {
                "eu-west-1": {
                    "gdpr_required": True,
                    "max_toxicity": 3.0,
                    "max_bias": 2.0
                },
                "us-east-1": {
                    "gdpr_required": False,
                    "max_toxicity": 5.0,
                    "max_bias": 4.0
                }
            },
            "category_restrictions": {
                "children_toys": {
                    "max_toxicity": 1.0,
                    "max_bias": 1.0,
                    "max_hallucination": 2.0
                },
                "healthcare": {
                    "max_toxicity": 2.0,
                    "max_bias": 1.0,
                    "max_hallucination": 1.0
                },
                "electronics": {
                    "max_toxicity": 5.0,
                    "max_bias": 4.0,
                    "max_hallucination": 6.0
                }
            }
        }
    
    def evaluate_content_policy(
        self, 
        analysis_result: Dict[str, Any], 
        context: PolicyContext
    ) -> PolicyResult:
        """
        Evaluate content against policies
        
        Args:
            analysis_result: Results from Bedrock analysis
            context: Policy evaluation context
            
        Returns:
            PolicyResult with decision and reasoning
        """
        reasons = []
        violations = []
        
        toxicity_score = analysis_result.get('toxicity_score', 0)
        bias_score = analysis_result.get('bias_score', 0)
        hallucination_score = analysis_result.get('hallucination_score', 0)
        
        # Check base thresholds
        toxicity_threshold = self.policies["toxicity"][context.compliance_mode]
        bias_threshold = self.policies["bias"][context.compliance_mode]
        hallucination_threshold = self.policies["hallucination"][context.compliance_mode]
        
        if toxicity_score > toxicity_threshold:
            reasons.append(PolicyReason.TOXICITY_THRESHOLD)
            violations.append(f"Toxicity score {toxicity_score} exceeds threshold {toxicity_threshold}")
        
        if bias_score > bias_threshold:
            reasons.append(PolicyReason.BIAS_THRESHOLD)
            violations.append(f"Bias score {bias_score} exceeds threshold {bias_threshold}")
        
        if hallucination_score > hallucination_threshold:
            reasons.append(PolicyReason.HALLUCINATION_THRESHOLD)
            violations.append(f"Hallucination score {hallucination_score} exceeds threshold {hallucination_threshold}")
        
        # Check regional compliance
        regional_policy = self.policies["regional_compliance"].get(context.region)
        if regional_policy:
            if toxicity_score > regional_policy.get("max_toxicity", float('inf')):
                reasons.append(PolicyReason.REGIONAL_COMPLIANCE)
                violations.append(f"Regional toxicity limit exceeded for {context.region}")
            
            if bias_score > regional_policy.get("max_bias", float('inf')):
                reasons.append(PolicyReason.REGIONAL_COMPLIANCE)
                violations.append(f"Regional bias limit exceeded for {context.region}")
        
        # Check category restrictions
        category_policy = self.policies["category_restrictions"].get(context.product_category)
        if category_policy:
            if toxicity_score > category_policy.get("max_toxicity", float('inf')):
                reasons.append(PolicyReason.CATEGORY_RESTRICTION)
                violations.append(f"Category toxicity limit exceeded for {context.product_category}")
            
            if bias_score > category_policy.get("max_bias", float('inf')):
                reasons.append(PolicyReason.CATEGORY_RESTRICTION)
                violations.append(f"Category bias limit exceeded for {context.product_category}")
            
            if hallucination_score > category_policy.get("max_hallucination", float('inf')):
                reasons.append(PolicyReason.CATEGORY_RESTRICTION)
                violations.append(f"Category hallucination limit exceeded for {context.product_category}")
        
        # Determine final decision
        if reasons:
            decision = PolicyDecision.DENY
            explanation = f"Content policy violations: {'; '.join(violations)}"
        else:
            decision = PolicyDecision.ALLOW
            reasons = [PolicyReason.APPROVED]
            explanation = "Content meets all policy requirements"
        
        return PolicyResult(
            decision=decision,
            reasons=reasons,
            explanation=explanation,
            metadata={
                "toxicity_score": toxicity_score,
                "bias_score": bias_score,
                "hallucination_score": hallucination_score,
                "thresholds_applied": {
                    "toxicity": toxicity_threshold,
                    "bias": bias_threshold,
                    "hallucination": hallucination_threshold
                },
                "context": {
                    "region": context.region,
                    "product_category": context.product_category,
                    "compliance_mode": context.compliance_mode
                }
            }
        )
    
    def evaluate_summary_policy(
        self, 
        summary_data: Dict[str, Any], 
        context: PolicyContext
    ) -> PolicyResult:
        """
        Evaluate summary generation policy
        
        Args:
            summary_data: Summary generation data
            context: Policy evaluation context
            
        Returns:
            PolicyResult for summary approval
        """
        reasons = []
        violations = []
        
        # Check if summary contains any flagged content
        reviews_excluded = summary_data.get('reviews_excluded', 0)
        total_reviews = summary_data.get('total_reviews', 1)
        exclusion_rate = reviews_excluded / total_reviews if total_reviews > 0 else 0
        
        # If too many reviews were excluded, flag for manual review
        if exclusion_rate > 0.5:  # More than 50% excluded
            reasons.append(PolicyReason.REGIONAL_COMPLIANCE)
            violations.append(f"High exclusion rate: {exclusion_rate:.2%} of reviews excluded")
        
        # Check summary quality metrics if available
        quality_score = summary_data.get('quality_score', 10)  # Default high quality
        if quality_score < 5:
            reasons.append(PolicyReason.HALLUCINATION_THRESHOLD)
            violations.append(f"Summary quality score {quality_score} below threshold")
        
        # Determine decision
        if reasons:
            decision = PolicyDecision.DENY
            explanation = f"Summary policy violations: {'; '.join(violations)}"
        else:
            decision = PolicyDecision.ALLOW
            reasons = [PolicyReason.APPROVED]
            explanation = "Summary meets all policy requirements"
        
        return PolicyResult(
            decision=decision,
            reasons=reasons,
            explanation=explanation,
            metadata={
                "exclusion_rate": exclusion_rate,
                "quality_score": quality_score,
                "context": {
                    "region": context.region,
                    "product_category": context.product_category,
                    "compliance_mode": context.compliance_mode
                }
            }
        )
    
    def update_policy_thresholds(self, policy_updates: Dict[str, Any]) -> None:
        """
        Update policy thresholds dynamically
        
        Args:
            policy_updates: Dictionary of policy updates
        """
        try:
            for policy_type, updates in policy_updates.items():
                if policy_type in self.policies:
                    self.policies[policy_type].update(updates)
                    logger.info(f"Updated {policy_type} policy: {updates}")
                else:
                    logger.warning(f"Unknown policy type: {policy_type}")
        except Exception as e:
            logger.error(f"Failed to update policies: {e}")
            raise
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """Get current policy configuration summary"""
        return {
            "policy_version": "1.0.0",
            "last_updated": "2024-01-01T00:00:00Z",
            "policies": self.policies
        }

# Global policy engine instance
policy_engine = PolicyEngine()

def evaluate_content_policy(analysis_result: Dict[str, Any], context: PolicyContext) -> PolicyResult:
    """Convenience function for content policy evaluation"""
    return policy_engine.evaluate_content_policy(analysis_result, context)

def evaluate_summary_policy(summary_data: Dict[str, Any], context: PolicyContext) -> PolicyResult:
    """Convenience function for summary policy evaluation"""
    return policy_engine.evaluate_summary_policy(summary_data, context)