---
name: Stack-AWS
description: AWS managed-service name patterns and their diagram node types — used by diagram synthesis tasks to categorize CONNECTS_TO targets
metadata:
  type: stack
  platform: aws
  detect-files:
    - "*.tf"
    - "requirements.txt"
    - "go.mod"
    - "package.json"
---

# Stack: AWS Services

Reference for categorising AWS service names found in `CONNECTS_TO` fields during diagram synthesis.
When a CONNECTS_TO target matches a name below, use the specified Mermaid node type instead of `:::unknown`.

## Managed data stores → cylinder `[(...)]` with `:::db`

| Name pattern | Label |
|---|---|
| `s3`, `s3-bucket`, `s3bucket` | S3 |
| `rds`, `aurora`, `postgres`, `mysql`, `mariadb` | RDS / Aurora |
| `dynamodb`, `dynamo` | DynamoDB |
| `elasticache`, `redis`, `memcached` | ElastiCache |
| `redshift` | Redshift |
| `opensearch`, `elasticsearch` | OpenSearch |
| `documentdb` | DocumentDB |
| `timestream` | Timestream |
| `keyspaces` | Keyspaces |

## Message queues / streams → parallelogram `[/.../]` with `:::q`

| Name pattern | Label |
|---|---|
| `sqs`, `sqs/<queue-name>` | SQS queue |
| `kinesis` | Kinesis |
| `msk`, `kafka` | MSK / Kafka |
| `eventbridge`, `event-bridge` | EventBridge |
| `sns` | SNS |

## Managed / external services → rectangle with `:::external`

These are AWS-managed control-plane or AI services that behave like external APIs from the application's perspective.

| Name pattern | Label |
|---|---|
| `bedrock`, `aws-bedrock` | AWS Bedrock |
| `sts`, `aws-sts`, `aws sts` | AWS STS |
| `acm`, `aws-acm` | ACM |
| `ecr`, `ecrregistry` | ECR |
| `cognito`, `aws-cognito` | Cognito |
| `ses`, `aws-ses` | SES |
| `secrets-manager`, `secretsmanager` | Secrets Manager |
| `ssm`, `parameter-store` | SSM |
| `kms` | KMS |
| `cloudwatch`, `cloudwatch-logs` | CloudWatch |
| `cloudfront` | CloudFront |
| `waf`, `aws-waf` | WAF |
| `route53` | Route 53 |
| `lambda` | Lambda |
| `glue` | Glue |
| `athena` | Athena |
| `rekognition` | Rekognition |
| `textract` | Textract |
| `comprehend` | Comprehend |
| `translate` | Translate |
| `polly` | Polly |
| `transcribe` | Transcribe |

## Matching rules

- Match case-insensitively against the target name in `CONNECTS_TO`.
- A name like `sqs/dataset-conversion` matches the `sqs` pattern — keep the full queue name as the label.
- If a target contains `secretspem`, `secretspem-file`, or is a Secrets Manager path, treat it as `:::external` Secrets Manager.
- Targets that don't match any pattern AND aren't a recognisable internal service: use `:::unknown` with the raw name.
