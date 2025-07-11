#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AIComplianceAuditorStack } from './ai-compliance-auditor-stack';

const app = new cdk.App();

new AIComplianceAuditorStack(app, 'AIComplianceAuditorStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description: 'AI Compliance Auditor for E-Commerce Review Moderation and Summarization',
});

app.synth();