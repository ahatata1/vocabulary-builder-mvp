Vocabulary Builder MVP

Serverless AI-powered vocabulary learning pipeline built on AWS.

This project processes uploaded PDF learning materials, extracts text using Amazon Textract, and generates vocabulary exercises using Amazon Bedrock (Claude 3 Haiku). The architecture follows an event-driven, asynchronous serverless design using AWS managed services.

---

Project Overview

The goal of this MVP is to help students upload educational PDFs and automatically generate interactive learning exercises such as:

- Multiple Choice Questions (MCQ)
- Fill-in-the-Blank exercises
- Vocabulary-focused learning content

The system is designed to be:

- Scalable
- Event-driven
- Serverless
- Cost-efficient
- Secure

---

Architecture

User Uploads PDF
        │
        ▼
S3 Bucket (raw/)
        │
        ▼
Lambda 1 — SubmitTextractJob
        │
        ▼
Amazon Textract (Async)
        │
        ▼
SNS Notification
        │
        ▼
Lambda 2 — FetchTextractResult
        │
        ▼
DynamoDB
(status = TEXTRACT_DONE)
        │
        ▼
DynamoDB Streams
        │
        ▼
Lambda 3 — GenerateExercises
        │
        ▼
Amazon Bedrock (Claude 3 Haiku)
        │
        ▼
DynamoDB
(status = EXERCISES_DONE)

---

AWS Services Used

- Amazon S3
- AWS Lambda
- Amazon Textract
- Amazon SNS
- Amazon DynamoDB
- DynamoDB Streams
- Amazon Bedrock
- Amazon CloudFront
- Amazon Cognito
- AWS IAM
- Amazon CloudWatch

---

Key Features

Asynchronous Document Processing

Uses Amazon Textract async APIs for scalable PDF processing.

Event-Driven Architecture

Pipeline built around S3 events, SNS notifications, and DynamoDB Streams.

AI Exercise Generation

Uses Claude 3 Haiku via Amazon Bedrock to generate:

- 5 MCQs
- 5 Fill-in-the-Blank exercises

Secure Infrastructure

- Private S3 buckets
- CloudFront OAC
- Least-privilege IAM
- Encryption enabled
- Lifecycle policies

---

DynamoDB Design

Single-table design:

PK = USER#<sub>
SK = PDF#<docId>

Document lifecycle:

TEXTRACT_SUBMITTED
→ TEXTRACT_DONE
→ EXERCISES_DONE

---

Repository Structure

vb_aws_project/
│
├── lambdas/
├── infrastructure/
├── scripts/
├── frontend/
├── docs/
└── screenshots/

---

Current Status

Completed

- CloudFront + OAC
- S3 secure storage
- Cognito authentication
- Lambda async Textract pipeline
- SNS integration
- DynamoDB integration
- Bedrock exercise generation
- Event-driven orchestration

In Progress

- README enhancements
- Architecture diagrams
- Screenshots
- LinkedIn portfolio optimization

---

Security Highlights

- S3 Block Public Access enabled
- SSE-S3 encryption
- Versioning enabled
- Lifecycle rules configured
- CloudFront HTTPS-only
- IAM least-privilege policies

---

Future Improvements

- Frontend dashboard
- API Gateway integration
- User progress tracking
- Flashcards system
- Quiz history
- CI/CD pipelines
- Infrastructure as Code refinement
- Monitoring dashboards

---

Screenshots

Screenshots and architecture diagrams will be added soon.

---

Author

Amr Hatata

AWS | Serverless | AI Integration | Cloud Engineering