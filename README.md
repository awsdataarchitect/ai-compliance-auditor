# AI Compliance Auditor for E-Commerce

A serverless AI-powered system for moderating and summarizing product reviews using **Amazon Nova Premier** with comprehensive audit trails and compliance reporting.

## 🚀 Overview

The AI Compliance Auditor provides enterprise-grade content moderation with:
- **AI Analysis**: Uses Amazon Nova Premier (inference profile) for intelligent toxicity, bias, and hallucination detection
- **Policy-Compliant Summarization**: Generates factual summaries while filtering out policy-violating content
- **Comprehensive Audit Trails**: Logs all AI decisions and processing steps for regulatory compliance
- **Real-time Monitoring**: CloudWatch dashboards for content moderation metrics
- **Flexible Compliance Modes**: Standard, strict, and mild compliance thresholds
- **Cross-Region Scalability**: Uses Nova Premier inference profiles for high availability

## 🏗️ Architecture

The system uses a serverless architecture built on AWS with AI integration:

### **Core Components**
- **AWS Step Functions**: Orchestrates the review processing pipeline
- **AWS Lambda**: Processes individual steps (analysis, validation, logging, summarization)
- **Amazon Bedrock Nova Premier**: AI analysis using inference profile `us.amazon.nova-premier-v1:0`
- **AWS Verified Permissions**: Cedar policy engine for content moderation
- **Amazon DynamoDB**: Structured audit log storage with TTL
- **Amazon OpenSearch**: Searchable audit logs and real-time dashboards
- **Amazon S3**: Compliance report storage
- **API Gateway**: RESTful API for review submission

### **AI Analysis Capabilities**
- **Toxicity Detection**: Identifies hate speech, harassment, threats, profanity
- **Bias Detection**: Detects unfair generalizations and discriminatory language
- **Hallucination Detection**: Identifies false claims and impossible statements
- **Intelligent Summarization**: Context-aware review summaries based on sentiment

### **Compliance Modes**
- **Standard Mode**: Balanced thresholds (Toxicity: 5, Bias: 4, Hallucination: 6)
- **Strict Mode**: Conservative thresholds (Toxicity: 3, Bias: 2, Hallucination: 4)
- **Mild Mode**: Permissive thresholds (Toxicity: 8, Bias: 7, Hallucination: 8)

## 📁 Project Structure

```
├── src/                          # CDK TypeScript infrastructure code
│   ├── app.ts                   # CDK app entry point
│   └── ai-compliance-auditor-stack.ts  # Main stack definition
├── lambda/                       # Lambda function code
│   ├── common/                  # Shared utilities
│   ├── layers/shared/           # Lambda layer dependencies
│   ├── review-auditor/          # Nova Premier analysis Lambda
│   │   └── handler.py           # Bedrock integration
│   ├── policy-validator/        # Policy validation Lambda
│   ├── review-summarizer/       # AI summarization Lambda
│   │   └── handler.py          # Nova Premier summarization
│   ├── audit-logger/           # Audit logging Lambda
│   └── report-generator/       # Report generation Lambda
├── scripts/                     # Build and deployment scripts
```

## 🚀 Getting Started

### Prerequisites

- Node.js 20+ and npm
- Python 3.12+
- AWS CLI configured with appropriate permissions
- AWS CDK CLI v2.156.0+
- **Amazon Bedrock access** with Nova Premier model enabled

### Installation

1. **Clone and install dependencies:**
```bash
git clone <repository-url>
cd impetus
npm install
```

2. **Build Lambda layer dependencies:**
```bash
chmod +x scripts/build-layer.sh
./scripts/build-layer.sh
```

3. **Build the CDK project:**
```bash
npm run build
```

4. **Bootstrap CDK (first time only):**
```bash
npx cdk bootstrap
```

5. **Deploy the infrastructure:**
```bash
npm run deploy
```

### 🔑 Required AWS Permissions

The system requires the following IAM permissions for Nova Premier:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:Converse",
        "bedrock:ConverseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/amazon.nova-premier-v1:0",
        "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-premier-v1:0"
      ]
    }
  ]
}
```

## 🧪 Testing the System

### Step-by-Step Testing Guide

#### 1. Get Your API Endpoint
After deployment, find your API Gateway URL in the CDK output:
```bash
npm run deploy
# Look for: ReviewSubmissionEndpoint = https://<your-api-id>.execute-api.us-east-1.amazonaws.com/v1/reviews
```

#### 2. Test Positive Review (Should be APPROVED)
```bash
curl -X POST https://<your-api-id>.execute-api.us-east-1.amazonaws.com/v1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test-product-001",
    "user_id": "test-user-001",
    "content": "Great product! Works well and arrived quickly. Good value for money.",
    "rating": 4,
    "region": "us-east-1",
    "product_category": "electronics",
    "compliance_mode": "standard"
  }'
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "result": "SUCCESS",
  "policy_decision": "APPROVED",
  "analysis_summary": {
    "toxicity_score": 0,
    "bias_score": 0,
    "hallucination_score": 0
  },
  "summary": "This product is highly rated for its quality, functionality, and value, with quick delivery.",
  "policy_reasons": ["CONTENT_APPROVED"]
}
```

#### 3. Test Negative Review with Standard Compliance
```bash
curl -X POST https://<your-api-id>.execute-api.us-east-1.amazonaws.com/v1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test-product-002",
    "user_id": "test-user-002",
    "content": "This product is terrible! It broke immediately and the company refuses to help.",
    "rating": 1,
    "region": "us-east-1",
    "product_category": "electronics",
    "compliance_mode": "standard"
  }'
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "result": "SUCCESS",
  "policy_decision": "APPROVED",
  "analysis_summary": {
    "toxicity_score": 2,
    "bias_score": 1,
    "hallucination_score": 5
  },
  "summary": "The product received poor feedback for breaking immediately and lacking company support.",
  "policy_reasons": ["CONTENT_APPROVED"]
}
```

#### 4. Test Same Review with Strict Compliance (Should be REJECTED)
```bash
curl -X POST https://<your-api-id>.execute-api.us-east-1.amazonaws.com/v1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test-product-003",
    "user_id": "test-user-003",
    "content": "This product is terrible! It broke immediately and the company refuses to help.",
    "rating": 1,
    "region": "us-east-1",
    "product_category": "electronics",
    "compliance_mode": "strict"
  }'
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "result": "REJECTED",
  "policy_decision": "DENIED",
  "analysis_summary": {
    "toxicity_score": 2,
    "bias_score": 1,
    "hallucination_score": 5
  },
  "policy_reasons": ["HALLUCINATION_THRESHOLD_EXCEEDED"],
  "rejection_explanation": "Content rejected based on strict compliance mode"
}
```

#### 5. Test Invalid Request (Should return validation error)
```bash
curl -X POST https://<your-api-id>.execute-api.us-east-1.amazonaws.com/v1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test-product-004",
    "user_id": "test-user-004",
    "content": "Short",
    "rating": 4,
    "region": "us-east-1",
    "product_category": "electronics",
    "compliance_mode": "standard"
  }'
```

**Expected Response:**
```json
{
  "message": "Invalid request body"
}
```

#### 6. Verify System Components

**Check Step Functions Execution:**
```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:<account-id>:stateMachine:ai-compliance-auditor-workflow \
  --region us-east-1
```

**Check Audit Logs in DynamoDB:**
```bash
aws dynamodb scan \
  --table-name ai-compliance-audit-logs \
  --limit 5 \
  --region us-east-1
```

**Check CloudWatch Logs:**
```bash
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/ai-compliance" \
  --region us-east-1
```

### Testing Different Scenarios

| Test Case | Compliance Mode | Expected Result | Purpose |
|-----------|----------------|-----------------|---------|
| Positive review | Standard | APPROVED | Verify normal operation |
| Negative review | Standard | APPROVED | Test nuanced analysis |
| Negative review | Strict | REJECTED | Test policy flexibility |
| Short content | Any | Validation Error | Test input validation |
| Different categories | Standard | APPROVED | Test category handling |

### Performance Testing
- **Response Time**: Should be 3-5 seconds for AI analysis
- **Success Rate**: Should be 100% for valid requests
- **Concurrent Requests**: System handles multiple simultaneous requests

### Troubleshooting
- **500 errors**: Check CloudWatch logs for Lambda function errors
- **Timeout**: Verify Bedrock model availability and permissions
- **Validation errors**: Ensure request body matches required schema

## 🔧 Development

### Available Scripts

- `npm run build` - Compile TypeScript to JavaScript
- `npm run watch` - Watch for changes and rebuild automatically
- `npm test` - Run Jest tests
- `npm run cdk` - Run CDK CLI commands
- `npm run deploy` - Deploy the stack to AWS
- `npm run destroy` - Destroy the stack from AWS
- `npm run synth` - Synthesize CloudFormation template
- `npm run diff` - Show differences between deployed and local stack

### Testing

Run the test suite:
```bash
npm test
```

Run tests in watch mode:
```bash
npm run test -- --watch
```

### Deployment

Deploy to AWS:
```bash
npm run deploy
```

Deploy with specific context:
```bash
npx cdk deploy --context environment=prod
```

Check what will be deployed:
```bash
npm run diff
```

## ⚙️ Configuration

The system uses AWS Systems Manager Parameter Store for configuration:

- `/ai-compliance/toxicity_threshold`: Maximum allowed toxicity score (0-10)
- `/ai-compliance/bias_threshold`: Maximum allowed bias score (0-10)
- `/ai-compliance/hallucination_threshold`: Maximum allowed hallucination score (0-10)
- `/ai-compliance/bedrock_model_id`: Nova Premier inference profile ID
- `/ai-compliance/prompt_version`: Prompt template version

## 📊 AI Analysis Examples

### Positive Review Analysis
```json
{
  "toxicity_score": 0,
  "bias_score": 0,
  "hallucination_score": 0,
  "explanations": {
    "toxicity": "The review contains no hate speech, harassment, threats, profanity, offensive language, or personal attacks.",
    "bias": "The review does not exhibit unfair generalizations, discriminatory language, or prejudiced statements.",
    "hallucination": "The statements made in the review are factual and do not contain false claims, impossible statements, or contradictions."
  }
}
```

### Negative Review Analysis
```json
{
  "toxicity_score": 2,
  "bias_score": 1,
  "hallucination_score": 5,
  "explanations": {
    "toxicity": "Review expresses frustration but contains no personal attacks or hate speech.",
    "bias": "No discriminatory language detected.",
    "hallucination": "Some claims about product failure may require verification."
  }
}
```

## 📈 Monitoring & Observability

- **CloudWatch**: Lambda function metrics and logs
- **DynamoDB**: Complete audit trail with AI explanations
- **Step Functions**: Workflow execution monitoring

### Key Metrics
- **Processing Time**: ~3-5 seconds for AI analysis
- **Success Rate**: 100% for valid requests
- **AI Model**: Amazon Nova Premier inference profile
- **Throughput**: Scales automatically with demand

## 🔒 Security & Compliance

- **Data Encryption**: All data encrypted at rest and in transit
- **VPC Isolation**: Sensitive components isolated in private subnets
- **IAM Roles**: Least privilege access with specific Bedrock permissions
- **SSL/TLS**: Enforced for all API endpoints
- **Audit Logging**: Complete trail of all AI decisions and policy applications
- **TTL Cleanup**: Automatic data retention management

## 🌟 Key Features

### ✅ AI Integration
- Amazon Nova Premier inference profile
- Cross-region availability and scaling
- Intelligent content analysis with explanations

### ✅ Flexible Policy Engine
- Multiple compliance modes
- Configurable thresholds
- Cedar-based policy validation

### ✅ Complete Audit Trail
- Every AI decision logged
- Policy application tracking
- Regulatory compliance ready

### ✅ Production Ready
- Serverless architecture
- Auto-scaling capabilities
- Comprehensive monitoring

## 🚀 Performance

- **Cold Start**: ~800ms (Lambda initialization)
- **Warm Execution**: ~3-5 seconds (AI processing)
- **Throughput**: Unlimited (serverless scaling)
- **Availability**: 99.9% (multi-AZ deployment)

## 📄 API Documentation

### Endpoints

#### POST /v1/reviews
Submit a review for AI analysis and compliance checking.

**Request Body:**
- `product_id` (string, required): Unique product identifier
- `user_id` (string, required): User identifier
- `content` (string, required): Review content (10-5000 characters)
- `rating` (number, required): Rating 1-5
- `region` (string, required): AWS region
- `product_category` (string, required): Product category
- `compliance_mode` (string, required): "standard", "strict", or "mild"

**Response:**
- `statusCode` (number): HTTP status code
- `result` (string): "SUCCESS" or "REJECTED"
- `policy_decision` (string): "APPROVED" or "DENIED"
- `analysis_summary` (object): AI analysis scores
- `summary` (string): AI-generated summary (if approved)
- `policy_reasons` (array): Reasons for decision

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the CloudWatch logs
2. Review the audit trail in DynamoDB
3. Monitor Step Functions execution
4. Check Bedrock model availability

## 🔗 Related Resources

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Nova Premier Model Guide](https://docs.aws.amazon.com/nova/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Step Functions Documentation](https://docs.aws.amazon.com/step-functions/)
