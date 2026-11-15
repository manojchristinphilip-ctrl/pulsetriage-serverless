# PulseTriage: Zero-Pipeline Autonomous Incident Triage

An event-driven serverless incident triage agent built for the **AWS Builder Center Weekend Challenge: No Pipeline, No Problem**. It intercepts application errors via Amazon EventBridge, deduplicates repeat failures in DynamoDB, diagnoses root causes with Amazon Bedrock, and delivers actionable fix alerts via Amazon SNS—with zero servers or deployment pipelines.

## Architecture
```text
[Application Error] 
       │
       ▼
[Amazon EventBridge] ──(Matches custom error pattern)──► [AWS Lambda (Python 3.12)]
                                                                │
                         ┌──────────────────────────────────────┼──────────────────────────────────────┐
                         ▼                                      ▼                                      ▼
               [Amazon DynamoDB]                       [Amazon Bedrock]                        [Amazon SNS]
           (SHA-256 Deduplication &                 (Amazon Nova Lite Root-               (Formatted Fix Alert to
              Occurrence Counter)                    Cause & Severity Analysis)               On-Call Engineer)
