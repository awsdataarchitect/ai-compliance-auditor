#!/bin/bash

# AI Compliance Auditor MVP Deployment Script
# This script deploys the basic MVP infrastructure to AWS

set -e

echo "🚀 Starting AI Compliance Auditor MVP Deployment"
echo "================================================"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK not found. Please install it with: npm install -g aws-cdk"
    exit 1
fi

# Get current AWS account and region
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

echo "📋 Deployment Configuration:"
echo "   AWS Account: $ACCOUNT"
echo "   AWS Region: $REGION"
echo "   Stack Name: AIComplianceAuditorStack"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
if [ -f "package.json" ]; then
    npm install
else
    echo "⚠️  No package.json found. Creating basic CDK project..."
    npm init -y
    npm install aws-cdk-lib constructs
fi

# Build Lambda layer
echo "🔧 Building Lambda layer..."
if [ -f "scripts/build-layer.sh" ]; then
    chmod +x scripts/build-layer.sh
    ./scripts/build-layer.sh
else
    echo "⚠️  Lambda layer build script not found. Creating basic layer..."
    mkdir -p lambda/layers/shared/python
    echo "boto3==1.34.0" > lambda/layers/shared/requirements.txt
    echo "pydantic==2.5.0" >> lambda/layers/shared/requirements.txt
fi

# Bootstrap CDK (if needed)
echo "🏗️  Bootstrapping CDK..."
cdk bootstrap aws://$ACCOUNT/$REGION || echo "CDK already bootstrapped"

# Synthesize the stack
echo "🔍 Synthesizing CDK stack..."
cdk synth

# Deploy the stack
echo "🚀 Deploying AI Compliance Auditor MVP..."
cdk deploy --require-approval never

# Get stack outputs
echo ""
echo "✅ Deployment completed successfully!"
echo "📊 Stack Outputs:"
cdk list --long 2>/dev/null || echo "Stack deployed successfully"

echo ""
echo "🎉 AI Compliance Auditor MVP is now deployed!"
echo ""
echo "📝 Next Steps:"
echo "1. Test the API Gateway endpoint for review submission"
echo "2. Monitor the CloudWatch dashboard for system health"
echo "3. Check DynamoDB tables for audit logs"
echo "4. Review S3 bucket for generated reports"
echo ""
echo "🔗 Useful Commands:"
echo "   View stack outputs: cdk list --long"
echo "   Update deployment: cdk deploy"
echo "   Destroy stack: cdk destroy"
echo ""
echo "📚 Documentation: Check the README.md for API usage examples"