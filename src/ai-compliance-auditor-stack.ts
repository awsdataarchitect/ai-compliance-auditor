import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

export class AIComplianceAuditorStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly sharedLambdaLayer: lambda.LayerVersion;
  public readonly auditTable: dynamodb.Table;
  public readonly reviewsTable: dynamodb.Table;
  public readonly summariesTable: dynamodb.Table;
  public readonly reportsBucket: s3.Bucket;
  
  // Lambda functions
  private _policyValidatorFunction!: lambda.Function;
  private _reviewSummarizerFunction!: lambda.Function;
  private _auditLoggerFunction!: lambda.Function;
  private _reviewAuditorFunction!: lambda.Function;
  
  // Step Functions
  private _complianceWorkflow!: stepfunctions.StateMachine;

  // Public getters for readonly access
  public get policyValidatorFunction(): lambda.Function { return this._policyValidatorFunction; }
  public get reviewSummarizerFunction(): lambda.Function { return this._reviewSummarizerFunction; }
  public get auditLoggerFunction(): lambda.Function { return this._auditLoggerFunction; }
  public get reviewAuditorFunction(): lambda.Function { return this._reviewAuditorFunction; }
  public get complianceWorkflow(): stepfunctions.StateMachine { return this._complianceWorkflow; }

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create VPC for secure networking
    this.vpc = new ec2.Vpc(this, 'AIComplianceVPC', {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
        {
          cidrMask: 24,
          name: 'Isolated',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    // Create shared Lambda layer for common dependencies
    this.sharedLambdaLayer = new lambda.LayerVersion(this, 'SharedLambdaLayer', {
      code: lambda.Code.fromAsset('lambda/layers/shared'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Shared dependencies for AI Compliance Auditor Lambda functions',
      layerVersionName: 'ai-compliance-shared-layer',
    });

    // Create DynamoDB table for audit logs
    this.auditTable = new dynamodb.Table(this, 'AuditTable', {
      tableName: 'ai-compliance-audit-logs',
      partitionKey: {
        name: 'audit_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES, // For real-time processing
    });

    // Add GSI for review_id lookups
    this.auditTable.addGlobalSecondaryIndex({
      indexName: 'review-id-index',
      partitionKey: {
        name: 'review_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add GSI for user_id lookups (for user-specific audit trails)
    this.auditTable.addGlobalSecondaryIndex({
      indexName: 'user-id-index',
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add GSI for product_id lookups (for product-specific analytics)
    this.auditTable.addGlobalSecondaryIndex({
      indexName: 'product-id-index',
      partitionKey: {
        name: 'product_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add GSI for event_type lookups (for event-specific queries)
    this.auditTable.addGlobalSecondaryIndex({
      indexName: 'event-type-index',
      partitionKey: {
        name: 'event_type',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Create DynamoDB table for reviews
    this.reviewsTable = new dynamodb.Table(this, 'ReviewsTable', {
      tableName: 'ai-compliance-reviews',
      partitionKey: {
        name: 'review_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
    });

    // Add GSI for product_id lookups on reviews table
    this.reviewsTable.addGlobalSecondaryIndex({
      indexName: 'product-id-index',
      partitionKey: {
        name: 'product_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add GSI for user_id lookups on reviews table
    this.reviewsTable.addGlobalSecondaryIndex({
      indexName: 'user-id-index',
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add GSI for status lookups on reviews table
    this.reviewsTable.addGlobalSecondaryIndex({
      indexName: 'status-index',
      partitionKey: {
        name: 'status',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Create DynamoDB table for review summaries
    this.summariesTable = new dynamodb.Table(this, 'SummariesTable', {
      tableName: 'ai-compliance-summaries',
      partitionKey: {
        name: 'summary_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
    });

    // Add GSI for product_id lookups on summaries table
    this.summariesTable.addGlobalSecondaryIndex({
      indexName: 'product-id-index',
      partitionKey: {
        name: 'product_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'generated_at',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Create S3 bucket for reports
    this.reportsBucket = new s3.Bucket(this, 'ReportsBucket', {
      bucketName: `ai-compliance-reports-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          enabled: true,
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development
      autoDeleteObjects: true, // For development
    });

    // Create IAM roles for Lambda functions
    this.createLambdaExecutionRoles();

    // Create Lambda functions
    this.createLambdaFunctions();
    
    // Create Step Functions workflow
    this.createStepFunctionsWorkflow();

    // Create basic CloudWatch monitoring
    this.createCloudWatchMonitoring();

    // Create API Gateway for review submission
    this.createApiGateway();

    // Output important resource ARNs
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'VPC ID for AI Compliance Auditor',
    });

    new cdk.CfnOutput(this, 'AuditTableName', {
      value: this.auditTable.tableName,
      description: 'DynamoDB table name for audit logs',
    });

    new cdk.CfnOutput(this, 'ReviewsTableName', {
      value: this.reviewsTable.tableName,
      description: 'DynamoDB table name for reviews',
    });

    new cdk.CfnOutput(this, 'SummariesTableName', {
      value: this.summariesTable.tableName,
      description: 'DynamoDB table name for summaries',
    });

    new cdk.CfnOutput(this, 'ReportsBucketName', {
      value: this.reportsBucket.bucketName,
      description: 'S3 bucket name for compliance reports',
    });

    new cdk.CfnOutput(this, 'ComplianceWorkflowArn', {
      value: this.complianceWorkflow.stateMachineArn,
      description: 'ARN of the AI Compliance Workflow Step Functions state machine',
    });
  }

  private createStepFunctionsWorkflow(): void {
    // Create Step Functions execution role
    const stepFunctionsRole = new iam.Role(this, 'StepFunctionsExecutionRole', {
      assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
      inlinePolicies: {
        LambdaInvokePolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['lambda:InvokeFunction'],
              resources: [
                this.reviewAuditorFunction.functionArn,
                this.policyValidatorFunction.functionArn,
                this.reviewSummarizerFunction.functionArn,
                this.auditLoggerFunction.functionArn,
              ],
            }),
          ],
        }),
      },
    });

    // Load Step Functions definition
    const workflowDefinition = stepfunctions.DefinitionBody.fromFile('src/step-functions/ai-compliance-workflow.json');

    // Create Step Functions state machine
    this._complianceWorkflow = new stepfunctions.StateMachine(this, 'ComplianceWorkflow', {
      stateMachineName: 'ai-compliance-auditor-workflow',
      definitionBody: workflowDefinition,
      role: stepFunctionsRole,
      timeout: cdk.Duration.minutes(15),
      tracingEnabled: true,
      logs: {
        destination: new logs.LogGroup(this, 'StepFunctionsLogGroup', {
          logGroupName: '/aws/stepfunctions/ai-compliance-auditor',
          retention: logs.RetentionDays.ONE_MONTH,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
        level: stepfunctions.LogLevel.ALL,
      },
    });
  }

  private createLambdaExecutionRoles(): void {
    // Base execution role for all Lambda functions
    const baseLambdaRole = new iam.Role(this, 'BaseLambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
      inlinePolicies: {
        BasePermissions: new iam.PolicyDocument({
          statements: [
            // CloudWatch Logs
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
              ],
              resources: ['arn:aws:logs:*:*:*'],
            }),
            // X-Ray tracing
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
              ],
              resources: ['*'],
            }),
            // Parameter Store for configuration
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ssm:GetParameter',
                'ssm:GetParameters',
                'ssm:GetParametersByPath',
              ],
              resources: [
                `arn:aws:ssm:${this.region}:${this.account}:parameter/ai-compliance/*`,
              ],
            }),
          ],
        }),
      },
    });

    // Bedrock access role for AI analysis functions
    const bedrockRole = new iam.Role(this, 'BedrockLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
      inlinePolicies: {
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream',
              ],
              resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/amazon.nova-premier-v1:0`,
              ],
            }),
          ],
        }),
      },
    });

    // DynamoDB and OpenSearch access role for audit logger
    const auditRole = new iam.Role(this, 'AuditLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
      inlinePolicies: {
        AuditAccess: new iam.PolicyDocument({
          statements: [
            // DynamoDB access
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:PutItem',
                'dynamodb:BatchWriteItem',
                'dynamodb:Query',
                'dynamodb:GetItem',
                'dynamodb:UpdateItem',
                'dynamodb:Scan',
              ],
              resources: [
                this.auditTable.tableArn,
                `${this.auditTable.tableArn}/index/*`,
                this.reviewsTable.tableArn,
                `${this.reviewsTable.tableArn}/index/*`,
                this.summariesTable.tableArn,
                `${this.summariesTable.tableArn}/index/*`,
              ],
            }),
            // CloudWatch Logs access for MVP
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
              ],
              resources: ['arn:aws:logs:*:*:*'],
            }),
          ],
        }),
      },
    });

    // Store roles as stack properties for use by other constructs
    (this as any).baseLambdaRole = baseLambdaRole;
    (this as any).bedrockRole = bedrockRole;
    (this as any).auditRole = auditRole;
  }

  private createLambdaFunctions(): void {
    // Combine Bedrock and audit permissions for Review Auditor
    const reviewAuditorRole = new iam.Role(this, 'ReviewAuditorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
      inlinePolicies: {
        ReviewAuditorPermissions: new iam.PolicyDocument({
          statements: [
            // CloudWatch Logs
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
              ],
              resources: ['arn:aws:logs:*:*:*'],
            }),
            // X-Ray tracing
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
              ],
              resources: ['*'],
            }),
            // Parameter Store for configuration
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'ssm:GetParameter',
                'ssm:GetParameters',
                'ssm:GetParametersByPath',
              ],
              resources: [
                `arn:aws:ssm:${this.region}:${this.account}:parameter/ai-compliance/*`,
              ],
            }),
            // Bedrock access for Nova Premier inference profile
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream',
                'bedrock:Converse',
                'bedrock:ConverseStream',
              ],
              resources: [
                // Foundation model access (required for inference profiles)
                `arn:aws:bedrock:*::foundation-model/amazon.nova-premier-v1:0`,
                // Inference profile access (can be in any region)
                `arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-premier-v1:0`,
              ],
            }),
            // DynamoDB access
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:PutItem',
                'dynamodb:BatchWriteItem',
                'dynamodb:Query',
                'dynamodb:GetItem',
                'dynamodb:UpdateItem',
              ],
              resources: [
                this.auditTable.tableArn,
                `${this.auditTable.tableArn}/index/*`,
                this.reviewsTable.tableArn,
                `${this.reviewsTable.tableArn}/index/*`,
              ],
            }),
            // CloudWatch metrics
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'cloudwatch:PutMetricData',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // Create Review Auditor Lambda function
    this._reviewAuditorFunction = new lambda.Function(this, 'ReviewAuditorFunction', {
      functionName: 'ai-compliance-review-auditor',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset('lambda/review-auditor'),
      layers: [this.sharedLambdaLayer],
      role: reviewAuditorRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      environment: {
        AUDIT_TABLE_NAME: this.auditTable.tableName,
        REVIEWS_TABLE_NAME: this.reviewsTable.tableName,
        SUMMARIES_TABLE_NAME: this.summariesTable.tableName,
        REPORTS_BUCKET_NAME: this.reportsBucket.bucketName,
        // OPENSEARCH_ENDPOINT removed for MVP
        DEPLOYMENT_REGION: this.region,
        ENVIRONMENT: 'production',
      },
      tracing: lambda.Tracing.ACTIVE,
      reservedConcurrentExecutions: 100, // Limit concurrent executions
      deadLetterQueue: new sqs.Queue(this, 'ReviewAuditorDLQ', {
        queueName: 'ai-compliance-review-auditor-dlq',
        retentionPeriod: cdk.Duration.days(14),
      }),
    });

    // Add CloudWatch alarms for the Review Auditor function
    new cloudwatch.Alarm(this, 'ReviewAuditorErrorAlarm', {
      alarmName: 'ai-compliance-review-auditor-errors',
      metric: this.reviewAuditorFunction.metricErrors({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    new cloudwatch.Alarm(this, 'ReviewAuditorDurationAlarm', {
      alarmName: 'ai-compliance-review-auditor-duration',
      metric: this.reviewAuditorFunction.metricDuration({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 240000, // 4 minutes (80% of timeout)
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Create Policy Validator Lambda function
    this._policyValidatorFunction = new lambda.Function(this, 'PolicyValidatorFunction', {
      functionName: 'ai-compliance-policy-validator',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset('lambda/policy-validator'),
      layers: [this.sharedLambdaLayer],
      role: (this as any).baseLambdaRole,
      timeout: cdk.Duration.minutes(2),
      memorySize: 512,
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      environment: {
        DEPLOYMENT_REGION: this.region,
        ENVIRONMENT: 'production',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Create Review Summarizer Lambda function
    this._reviewSummarizerFunction = new lambda.Function(this, 'ReviewSummarizerFunction', {
      functionName: 'ai-compliance-review-summarizer',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset('lambda/review-summarizer'),
      layers: [this.sharedLambdaLayer],
      role: reviewAuditorRole, // Reuse role with Bedrock access
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      environment: {
        AUDIT_TABLE_NAME: this.auditTable.tableName,
        REVIEWS_TABLE_NAME: this.reviewsTable.tableName,
        SUMMARIES_TABLE_NAME: this.summariesTable.tableName,
        REPORTS_BUCKET_NAME: this.reportsBucket.bucketName,
        DEPLOYMENT_REGION: this.region,
        ENVIRONMENT: 'production',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Create Audit Logger Lambda function
    this._auditLoggerFunction = new lambda.Function(this, 'AuditLoggerFunction', {
      functionName: 'ai-compliance-audit-logger',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset('lambda/audit-logger'),
      layers: [this.sharedLambdaLayer],
      role: (this as any).auditRole,
      timeout: cdk.Duration.minutes(3),
      memorySize: 512,
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      environment: {
        AUDIT_TABLE_NAME: this.auditTable.tableName,
        REVIEWS_TABLE_NAME: this.reviewsTable.tableName,
        SUMMARIES_TABLE_NAME: this.summariesTable.tableName,
        DEPLOYMENT_REGION: this.region,
        ENVIRONMENT: 'production',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Output Lambda function ARNs
    new cdk.CfnOutput(this, 'ReviewAuditorFunctionArn', {
      value: this.reviewAuditorFunction.functionArn,
      description: 'ARN of the Review Auditor Lambda function',
    });

    new cdk.CfnOutput(this, 'PolicyValidatorFunctionArn', {
      value: this.policyValidatorFunction.functionArn,
      description: 'ARN of the Policy Validator Lambda function',
    });

    new cdk.CfnOutput(this, 'ReviewSummarizerFunctionArn', {
      value: this.reviewSummarizerFunction.functionArn,
      description: 'ARN of the Review Summarizer Lambda function',
    });

    new cdk.CfnOutput(this, 'AuditLoggerFunctionArn', {
      value: this.auditLoggerFunction.functionArn,
      description: 'ARN of the Audit Logger Lambda function',
    });
  }

  private createCloudWatchMonitoring(): void {
    // Create CloudWatch Dashboard for basic monitoring
    const dashboard = new cloudwatch.Dashboard(this, 'AIComplianceDashboard', {
      dashboardName: 'AI-Compliance-Auditor-MVP',
      widgets: [
        [
          // Lambda function metrics
          new cloudwatch.GraphWidget({
            title: 'Lambda Function Invocations',
            left: [
              this.reviewAuditorFunction.metricInvocations(),
              this.policyValidatorFunction.metricInvocations(),
              this.reviewSummarizerFunction.metricInvocations(),
              this.auditLoggerFunction.metricInvocations(),
            ],
            width: 12,
            height: 6,
          }),
          new cloudwatch.GraphWidget({
            title: 'Lambda Function Errors',
            left: [
              this.reviewAuditorFunction.metricErrors(),
              this.policyValidatorFunction.metricErrors(),
              this.reviewSummarizerFunction.metricErrors(),
              this.auditLoggerFunction.metricErrors(),
            ],
            width: 12,
            height: 6,
          }),
        ],
        [
          // Lambda duration metrics
          new cloudwatch.GraphWidget({
            title: 'Lambda Function Duration',
            left: [
              this.reviewAuditorFunction.metricDuration(),
              this.policyValidatorFunction.metricDuration(),
              this.reviewSummarizerFunction.metricDuration(),
              this.auditLoggerFunction.metricDuration(),
            ],
            width: 12,
            height: 6,
          }),
          // Step Functions metrics
          new cloudwatch.GraphWidget({
            title: 'Step Functions Executions',
            left: [
              this.complianceWorkflow.metricStarted(),
              this.complianceWorkflow.metricSucceeded(),
              this.complianceWorkflow.metricFailed(),
            ],
            width: 12,
            height: 6,
          }),
        ],
        [
          // DynamoDB metrics
          new cloudwatch.GraphWidget({
            title: 'DynamoDB Operations',
            left: [
              this.auditTable.metricConsumedReadCapacityUnits(),
              this.auditTable.metricConsumedWriteCapacityUnits(),
            ],
            width: 12,
            height: 6,
          }),
          // Custom metrics placeholder
          new cloudwatch.SingleValueWidget({
            title: 'System Health',
            metrics: [
              this.reviewAuditorFunction.metricInvocations({
                statistic: 'Sum',
                period: cdk.Duration.hours(1),
              }),
            ],
            width: 12,
            height: 6,
          }),
        ],
      ],
    });

    // Create basic alarms for system health
    new cloudwatch.Alarm(this, 'StepFunctionFailureAlarm', {
      alarmName: 'ai-compliance-step-function-failures',
      metric: this.complianceWorkflow.metricFailed({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 3,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'Alert when Step Functions workflow fails repeatedly',
    });

    new cloudwatch.Alarm(this, 'PolicyValidatorErrorAlarm', {
      alarmName: 'ai-compliance-policy-validator-errors',
      metric: this.policyValidatorFunction.metricErrors({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'Alert when Policy Validator has high error rate',
    });

    new cloudwatch.Alarm(this, 'ReviewSummarizerErrorAlarm', {
      alarmName: 'ai-compliance-review-summarizer-errors',
      metric: this.reviewSummarizerFunction.metricErrors({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'Alert when Review Summarizer has high error rate',
    });

    new cloudwatch.Alarm(this, 'AuditLoggerErrorAlarm', {
      alarmName: 'ai-compliance-audit-logger-errors',
      metric: this.auditLoggerFunction.metricErrors({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 10, // Higher threshold since audit logging is less critical
      evaluationPeriods: 3,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: 'Alert when Audit Logger has high error rate',
    });

    // Output dashboard URL
    new cdk.CfnOutput(this, 'CloudWatchDashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${dashboard.dashboardName}`,
      description: 'URL to the CloudWatch Dashboard for AI Compliance Auditor',
    });
  }

  private createApiGateway(): void {
    // Create API Gateway execution role
    const apiGatewayRole = new iam.Role(this, 'ApiGatewayExecutionRole', {
      assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      inlinePolicies: {
        StepFunctionsExecutionPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'states:StartExecution',
                'states:DescribeExecution',
                'states:GetExecutionHistory',
              ],
              resources: [this.complianceWorkflow.stateMachineArn],
            }),
          ],
        }),
      },
    });

    // Create REST API
    const api = new apigateway.RestApi(this, 'AIComplianceApi', {
      restApiName: 'AI Compliance Auditor API',
      description: 'API for submitting reviews for AI compliance auditing',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
      deployOptions: {
        stageName: 'v1',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
    });

    // Create /reviews resource
    const reviewsResource = api.root.addResource('reviews');

    // Create Step Functions integration
    const stepFunctionsIntegration = new apigateway.AwsIntegration({
      service: 'states',
      action: 'StartExecution',
      integrationHttpMethod: 'POST',
      options: {
        credentialsRole: apiGatewayRole,
        requestTemplates: {
          'application/json': JSON.stringify({
            stateMachineArn: this.complianceWorkflow.stateMachineArn,
            input: JSON.stringify({
              review_id: "$context.requestId",
              product_id: "$input.path('$.product_id')",
              user_id: "$input.path('$.user_id')",
              content: "$input.path('$.content')",
              rating: "$input.path('$.rating')",
              region: "$input.path('$.region')",
              product_category: "$input.path('$.product_category')",
              compliance_mode: "$input.path('$.compliance_mode')",
              api_request_id: "$context.requestId",
              source_ip: "$context.identity.sourceIp",
              user_agent: "$context.identity.userAgent"
            })
          })
        },
        integrationResponses: [
          {
            statusCode: '200',
            responseTemplates: {
              'application/json': JSON.stringify({
                message: 'Review submitted for processing',
                execution_arn: '$input.path($.executionArn)',
                request_id: '$context.requestId',
                status: 'PROCESSING'
              })
            },
          },
          {
            statusCode: '400',
            selectionPattern: '4\\d{2}',
            responseTemplates: {
              'application/json': JSON.stringify({
                error: 'Bad Request',
                message: 'Invalid request format',
                request_id: '$context.requestId'
              })
            },
          },
          {
            statusCode: '500',
            selectionPattern: '5\\d{2}',
            responseTemplates: {
              'application/json': JSON.stringify({
                error: 'Internal Server Error',
                message: 'Failed to process review',
                request_id: '$context.requestId'
              })
            },
          },
        ],
      },
    });

    // Add POST method for review submission
    reviewsResource.addMethod('POST', stepFunctionsIntegration, {
      requestValidator: new apigateway.RequestValidator(this, 'ReviewRequestValidator', {
        restApi: api,
        requestValidatorName: 'review-request-validator',
        validateRequestBody: true,
        validateRequestParameters: false,
      }),
      requestModels: {
        'application/json': new apigateway.Model(this, 'ReviewRequestModel', {
          restApi: api,
          modelName: 'ReviewRequest',
          contentType: 'application/json',
          schema: {
            type: apigateway.JsonSchemaType.OBJECT,
            required: ['product_id', 'user_id', 'content', 'rating'],
            properties: {
              product_id: {
                type: apigateway.JsonSchemaType.STRING,
                minLength: 1,
                maxLength: 100,
              },
              user_id: {
                type: apigateway.JsonSchemaType.STRING,
                minLength: 1,
                maxLength: 100,
              },
              content: {
                type: apigateway.JsonSchemaType.STRING,
                minLength: 10,
                maxLength: 5000,
              },
              rating: {
                type: apigateway.JsonSchemaType.INTEGER,
                minimum: 1,
                maximum: 5,
              },
              region: {
                type: apigateway.JsonSchemaType.STRING,
                enum: ['us-east-1', 'us-west-2', 'eu-west-1', 'eu-central-1', 'ap-southeast-1'],
              },
              product_category: {
                type: apigateway.JsonSchemaType.STRING,
                enum: ['electronics', 'clothing', 'books', 'toys', 'health', 'food', 'other'],
              },
              compliance_mode: {
                type: apigateway.JsonSchemaType.STRING,
                enum: ['mild', 'standard', 'strict'],
              },
            },
          },
        }),
      },
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
        {
          statusCode: '400',
          responseModels: {
            'application/json': apigateway.Model.ERROR_MODEL,
          },
        },
        {
          statusCode: '500',
          responseModels: {
            'application/json': apigateway.Model.ERROR_MODEL,
          },
        },
      ],
    });

    // Add GET method for execution status
    const executionResource = reviewsResource.addResource('{executionId}');
    
    // Create Step Functions describe execution integration
    const describeExecutionIntegration = new apigateway.AwsIntegration({
      service: 'states',
      action: 'DescribeExecution',
      integrationHttpMethod: 'POST',
      options: {
        credentialsRole: apiGatewayRole,
        requestTemplates: {
          'application/json': JSON.stringify({
            executionArn: "$method.request.path.executionId"
          })
        },
        integrationResponses: [
          {
            statusCode: '200',
            responseTemplates: {
              'application/json': JSON.stringify({
                execution_arn: '$input.path($.executionArn)',
                status: '$input.path($.status)',
                start_date: '$input.path($.startDate)',
                stop_date: '$input.path($.stopDate)',
                output: '$input.path($.output)'
              })
            },
          },
        ],
      },
    });

    executionResource.addMethod('GET', describeExecutionIntegration, {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
    });

    // Output API Gateway URL
    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'URL of the AI Compliance Auditor API Gateway',
    });

    new cdk.CfnOutput(this, 'ReviewSubmissionEndpoint', {
      value: `${api.url}reviews`,
      description: 'Endpoint for submitting reviews for compliance auditing',
    });
  }
}