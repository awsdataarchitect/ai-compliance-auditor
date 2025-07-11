"""
Review analysis functions using Bedrock Nova Premier model.
Provides comprehensive analysis for toxicity, bias, and hallucination detection.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from bedrock_client import bedrock_client, BedrockError
from models import Review, AnalysisResult, ModelMetadata
from config import config

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Custom exception for analysis errors."""
    pass


class ReviewAnalyzer:
    """Comprehensive review analyzer using Bedrock Nova Premier."""
    
    def __init__(self):
        self.bedrock = bedrock_client
        
        # Load thresholds from configuration
        self.toxicity_threshold = float(config.get_parameter('toxicity_threshold', '5.0'))
        self.bias_threshold = float(config.get_parameter('bias_threshold', '3.0'))
        self.hallucination_threshold = float(config.get_parameter('hallucination_threshold', '6.0'))
        
        logger.info(f"Initialized ReviewAnalyzer with thresholds - "
                   f"toxicity: {self.toxicity_threshold}, "
                   f"bias: {self.bias_threshold}, "
                   f"hallucination: {self.hallucination_threshold}")
    
    async def analyze_toxicity(self, content: str) -> Dict[str, Any]:
        """
        Analyze content for toxicity.
        
        Args:
            content: Review content to analyze
            
        Returns:
            Dictionary containing toxicity analysis results
        """
        try:
            result = await self.bedrock.analyze_toxicity(content)
            
            # Validate and normalize the response
            toxicity_score = float(result.get('toxicity_score', 0))
            explanation = result.get('explanation', 'No explanation provided')
            confidence = float(result.get('confidence', 0.5))
            detected_issues = result.get('detected_issues', [])
            
            # Ensure score is within valid range
            toxicity_score = max(0, min(10, toxicity_score))
            
            return {
                'toxicity_score': toxicity_score,
                'explanation': explanation,
                'confidence': confidence,
                'detected_issues': detected_issues,
                'threshold_exceeded': toxicity_score > self.toxicity_threshold,
                'model_metadata': result.get('model_metadata', {})
            }
            
        except BedrockError as e:
            logger.error(f"Bedrock error during toxicity analysis: {str(e)}")
            raise AnalysisError(f"Failed to analyze toxicity: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during toxicity analysis: {str(e)}")
            raise AnalysisError(f"Unexpected error in toxicity analysis: {str(e)}")
    
    async def analyze_bias(self, content: str) -> Dict[str, Any]:
        """
        Analyze content for bias and discrimination.
        
        Args:
            content: Review content to analyze
            
        Returns:
            Dictionary containing bias analysis results
        """
        try:
            result = await self.bedrock.analyze_bias(content)
            
            # Validate and normalize the response
            bias_score = float(result.get('bias_score', 0))
            explanation = result.get('explanation', 'No explanation provided')
            confidence = float(result.get('confidence', 0.5))
            bias_types = result.get('bias_types', [])
            problematic_phrases = result.get('problematic_phrases', [])
            
            # Ensure score is within valid range
            bias_score = max(0, min(10, bias_score))
            
            return {
                'bias_score': bias_score,
                'explanation': explanation,
                'confidence': confidence,
                'bias_types': bias_types,
                'problematic_phrases': problematic_phrases,
                'threshold_exceeded': bias_score > self.bias_threshold,
                'model_metadata': result.get('model_metadata', {})
            }
            
        except BedrockError as e:
            logger.error(f"Bedrock error during bias analysis: {str(e)}")
            raise AnalysisError(f"Failed to analyze bias: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during bias analysis: {str(e)}")
            raise AnalysisError(f"Unexpected error in bias analysis: {str(e)}")
    
    async def analyze_hallucination(self, content: str) -> Dict[str, Any]:
        """
        Analyze content for hallucinated or fabricated claims.
        
        Args:
            content: Review content to analyze
            
        Returns:
            Dictionary containing hallucination analysis results
        """
        try:
            result = await self.bedrock.analyze_hallucination(content)
            
            # Validate and normalize the response
            hallucination_score = float(result.get('hallucination_score', 0))
            explanation = result.get('explanation', 'No explanation provided')
            confidence = float(result.get('confidence', 0.5))
            questionable_claims = result.get('questionable_claims', [])
            realistic_claims = result.get('realistic_claims', [])
            
            # Ensure score is within valid range
            hallucination_score = max(0, min(10, hallucination_score))
            
            return {
                'hallucination_score': hallucination_score,
                'explanation': explanation,
                'confidence': confidence,
                'questionable_claims': questionable_claims,
                'realistic_claims': realistic_claims,
                'threshold_exceeded': hallucination_score > self.hallucination_threshold,
                'model_metadata': result.get('model_metadata', {})
            }
            
        except BedrockError as e:
            logger.error(f"Bedrock error during hallucination analysis: {str(e)}")
            raise AnalysisError(f"Failed to analyze hallucination: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during hallucination analysis: {str(e)}")
            raise AnalysisError(f"Unexpected error in hallucination analysis: {str(e)}")
    
    async def comprehensive_analysis(self, content: str) -> AnalysisResult:
        """
        Perform comprehensive analysis including toxicity, bias, and hallucination detection.
        
        Args:
            content: Review content to analyze
            
        Returns:
            AnalysisResult object with all analysis results
        """
        try:
            # Run all analyses concurrently for better performance
            toxicity_task = self.analyze_toxicity(content)
            bias_task = self.analyze_bias(content)
            hallucination_task = self.analyze_hallucination(content)
            
            toxicity_result, bias_result, hallucination_result = await asyncio.gather(
                toxicity_task, bias_task, hallucination_task
            )
            
            # Combine explanations
            explanations = {
                'toxicity': toxicity_result['explanation'],
                'bias': bias_result['explanation'],
                'hallucination': hallucination_result['explanation']
            }
            
            # Calculate confidence scores
            confidence_scores = {
                'toxicity': toxicity_result['confidence'],
                'bias': bias_result['confidence'],
                'hallucination': hallucination_result['confidence']
            }
            
            # Create AnalysisResult object
            analysis_result = AnalysisResult(
                toxicity_score=toxicity_result['toxicity_score'],
                bias_score=bias_result['bias_score'],
                hallucination_score=hallucination_result['hallucination_score'],
                explanations=explanations,
                confidence_scores=confidence_scores
            )
            
            logger.info(f"Completed comprehensive analysis - "
                       f"toxicity: {analysis_result.toxicity_score:.2f}, "
                       f"bias: {analysis_result.bias_score:.2f}, "
                       f"hallucination: {analysis_result.hallucination_score:.2f}")
            
            return analysis_result
            
        except AnalysisError:
            # Re-raise analysis errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error during comprehensive analysis: {str(e)}")
            raise AnalysisError(f"Failed to complete comprehensive analysis: {str(e)}")
    
    async def batch_analysis(self, reviews: List[str], max_concurrent: int = 5) -> List[AnalysisResult]:
        """
        Perform batch analysis on multiple reviews with concurrency control.
        
        Args:
            reviews: List of review content strings
            max_concurrent: Maximum number of concurrent analyses
            
        Returns:
            List of AnalysisResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(content: str) -> AnalysisResult:
            async with semaphore:
                return await self.comprehensive_analysis(content)
        
        try:
            tasks = [analyze_with_semaphore(content) for content in reviews]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            analysis_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to analyze review {i}: {str(result)}")
                    # Create a default analysis result for failed analyses
                    analysis_results.append(AnalysisResult(
                        toxicity_score=0.0,
                        bias_score=0.0,
                        hallucination_score=0.0,
                        explanations={
                            'toxicity': f'Analysis failed: {str(result)}',
                            'bias': f'Analysis failed: {str(result)}',
                            'hallucination': f'Analysis failed: {str(result)}'
                        }
                    ))
                else:
                    analysis_results.append(result)
            
            logger.info(f"Completed batch analysis of {len(reviews)} reviews")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Batch analysis failed: {str(e)}")
            raise AnalysisError(f"Batch analysis failed: {str(e)}")
    
    def get_analysis_summary(self, analysis_result: AnalysisResult) -> Dict[str, Any]:
        """
        Generate a summary of analysis results.
        
        Args:
            analysis_result: AnalysisResult object
            
        Returns:
            Dictionary containing analysis summary
        """
        # Determine overall risk level
        max_score = max(
            analysis_result.toxicity_score,
            analysis_result.bias_score,
            analysis_result.hallucination_score
        )
        
        if max_score >= 8:
            risk_level = "HIGH"
        elif max_score >= 5:
            risk_level = "MEDIUM"
        elif max_score >= 3:
            risk_level = "LOW"
        else:
            risk_level = "MINIMAL"
        
        # Check threshold violations
        violations = []
        if analysis_result.toxicity_score > self.toxicity_threshold:
            violations.append(f"toxicity ({analysis_result.toxicity_score:.1f} > {self.toxicity_threshold})")
        if analysis_result.bias_score > self.bias_threshold:
            violations.append(f"bias ({analysis_result.bias_score:.1f} > {self.bias_threshold})")
        if analysis_result.hallucination_score > self.hallucination_threshold:
            violations.append(f"hallucination ({analysis_result.hallucination_score:.1f} > {self.hallucination_threshold})")
        
        return {
            'risk_level': risk_level,
            'max_score': max_score,
            'threshold_violations': violations,
            'should_approve': len(violations) == 0,
            'scores': {
                'toxicity': analysis_result.toxicity_score,
                'bias': analysis_result.bias_score,
                'hallucination': analysis_result.hallucination_score
            },
            'confidence_scores': analysis_result.confidence_scores or {}
        }
    
    async def analyze_review_object(self, review: Review) -> Review:
        """
        Analyze a Review object and update it with analysis results.
        
        Args:
            review: Review object to analyze
            
        Returns:
            Updated Review object with analysis results
        """
        try:
            analysis_result = await self.comprehensive_analysis(review.content)
            review.analysis_result = analysis_result
            
            # Update review status based on analysis
            summary = self.get_analysis_summary(analysis_result)
            if summary['should_approve']:
                review.status = review.status  # Keep current status if approved
            else:
                review.processing_errors = [f"Policy violations: {', '.join(summary['threshold_violations'])}"]
            
            logger.info(f"Analyzed review {review.review_id} - risk level: {summary['risk_level']}")
            return review
            
        except Exception as e:
            logger.error(f"Failed to analyze review {review.review_id}: {str(e)}")
            review.processing_errors = [f"Analysis failed: {str(e)}"]
            raise AnalysisError(f"Failed to analyze review: {str(e)}")
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current analysis thresholds."""
        return {
            'toxicity_threshold': self.toxicity_threshold,
            'bias_threshold': self.bias_threshold,
            'hallucination_threshold': self.hallucination_threshold
        }
    
    def update_thresholds(self, toxicity: Optional[float] = None, 
                         bias: Optional[float] = None, 
                         hallucination: Optional[float] = None) -> None:
        """
        Update analysis thresholds.
        
        Args:
            toxicity: New toxicity threshold (0-10)
            bias: New bias threshold (0-10)
            hallucination: New hallucination threshold (0-10)
        """
        if toxicity is not None:
            self.toxicity_threshold = max(0, min(10, toxicity))
        if bias is not None:
            self.bias_threshold = max(0, min(10, bias))
        if hallucination is not None:
            self.hallucination_threshold = max(0, min(10, hallucination))
        
        logger.info(f"Updated thresholds - "
                   f"toxicity: {self.toxicity_threshold}, "
                   f"bias: {self.bias_threshold}, "
                   f"hallucination: {self.hallucination_threshold}")


# Global analyzer instance
review_analyzer = ReviewAnalyzer()