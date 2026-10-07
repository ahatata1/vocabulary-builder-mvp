# Vocabulary Builder MVP

## Phase 1 — AWS Foundation Engineering Troubleshooting Report

**Phase:** AWS Foundation  
**Status:** ✅ Completed / Resolved  
**Region:** `us-east-1`

---

## Overview

Phase 1 established the secure AWS foundation for the Vocabulary Builder MVP using Python/Boto3 and AWS managed services.

The final design uses:

- Separate private S3 buckets for website assets and user documents
- CloudFront with Origin Access Control (OAC) for public website delivery
- Cognito for managed authentication
- SSE-S3 encryption
- S3 versioning and lifecycle controls for documents
- Presigned URLs for controlled uploads
- IAM and bucket policies with clear resource dependencies

This report consolidates the hands-on implementation issues and the architecture/security troubleshooting history into one final Phase 1 record.

---

# Case 1 — AWS SDK and Local Development Environment

## Services / Tools Involved
- Python
- Boto3
- AWS credentials
- VS Code

## Problem
There was uncertainty whether the local development environment was correctly authenticated and able to communicate with AWS.

## Root Cause
Infrastructure automation could not be debugged reliably until credentials, Region configuration, and SDK connectivity were known to work.

## Final Solution
The Python/Boto3 environment was validated by executing AWS API operations. Successful S3 operations confirmed that the credentials and SDK configuration were functional.

## Engineering Lesson
Verify the execution environment and AWS authentication before debugging infrastructure logic.

---

# Case 2 — S3 Bucket Creation in us-east-1

## Service Involved
- Amazon S3
- Boto3

## Problem
Bucket creation behaved differently in `us-east-1` than examples written for other AWS Regions.

## Root Cause
For `us-east-1`, `CreateBucket` does not use the same `LocationConstraint` pattern normally supplied for other Regions.

## Final Solution

```python
s3.create_bucket(
    Bucket=bucket_name
)
```

## Result
Both project buckets could be created and configured successfully.

## Engineering Lesson
AWS APIs can have Region-specific behavior. Infrastructure automation should account for it explicitly.

---

# Case 3 — CloudFront + OAC + Private S3 Website Access

## Services Involved
- Amazon CloudFront
- Amazon S3
- Origin Access Control (OAC)

## Problem
The website needed to remain publicly reachable while the S3 origin stayed private.

After enabling S3 Block Public Access, direct/public access patterns no longer worked and CloudFront required an explicit trusted path to the origin.

## Root Cause
A private S3 origin was correct, but CloudFront had to be explicitly authorized to retrieve objects from it.

Public bucket policies or ACL-based access would conflict with the intended security model.

## Final Solution
Implemented:

- CloudFront OAC
- SigV4 request signing
- S3 Block Public Access
- `BucketOwnerEnforced`
- HTTPS redirect
- S3 bucket policy scoped to the real CloudFront distribution `SourceArn`

Final request path:

```text
Internet User
      │
      ▼
  CloudFront
      │
      │ SigV4
      ▼
     OAC
      │
      ▼
 Private S3
```

## Result
The website remained publicly available through CloudFront while the S3 origin remained private.

## Engineering Lesson
A public website does not require a public S3 bucket.

```text
Private S3 + CloudFront + OAC
```

is the correct access model for this project.

---

# Case 4 — BucketOwnerEnforced and ACL Simplification

## Service Involved
- Amazon S3

## Problem
Permissions became harder to reason about when ACLs, IAM policies, and bucket policies could all affect access.

## Root Cause
Multiple overlapping authorization mechanisms increase complexity and can create confusing permission behavior.

## Final Solution
Enabled:

```text
BucketOwnerEnforced
```

This disabled ACLs. Access is controlled using IAM policies and S3 bucket policies.

## Engineering Lesson
Reducing authorization layers makes the system easier to secure, audit, and troubleshoot.

---

# Case 5 — Single Bucket vs Two-Bucket Architecture

## Services Involved
- Amazon S3
- AWS IAM

## Problem
The project needed to decide whether static website files, uploaded PDFs, and processing outputs should share one bucket.

## Root Cause
A single bucket would mix public-delivery and private-processing responsibilities, increasing blast radius and policy complexity.

## Final Solution

### Website Bucket
```text
vb-website-2025
```

Purpose:

```text
CloudFront → OAC → Private S3 origin
```

### Documents Bucket
```text
vb-documents-2025
```

Purpose:

- User PDF uploads
- AI processing inputs
- Textract outputs
- Processing outputs

## Engineering Lesson
Workload isolation simplifies IAM, lifecycle management, auditing, and least-privilege design.

---

# Case 6 — Secure Document Storage Baseline

## Service Involved
- Amazon S3

## Problem
User PDFs needed to remain private while still being usable by backend processing services.

## Final Solution
Configured:

- Block Public Access
- `BucketOwnerEnforced`
- SSE-S3 (`AES256`)
- Versioning on `vb-documents-2025`

Object Lock and Cross-Region Replication were intentionally not added because the MVP did not require immutable retention or multi-region disaster recovery.

## Engineering Lesson
Good architecture is the simplest design that satisfies the actual security, availability, operational, and business requirements.

---

# Case 7 — Lifecycle Cost Optimization

## Service Involved
- Amazon S3

## Problem
Uploaded files and processing artifacts could accumulate indefinitely and increase storage cost.

## Final Solution
Lifecycle rules were configured:

| Prefix | Lifecycle |
|---|---:|
| `raw/` | 90 days |
| `textract-output/` | 730 days |
| `comprehend-output/` | 730 days |

## Engineering Lesson
Cost optimization belongs in the architecture from the beginning, not only after production growth.

---

# Case 8 — Presigned URL Upload Testing

## Services / Tools Involved
- Amazon S3
- Presigned URLs
- Postman

## Problem
There was confusion about how a presigned upload URL relates to the HTTP method, object key, query parameters, and file body.

## Root Cause
A presigned URL authorizes one specific S3 operation on a specific object key for a limited time. It is not a generic upload endpoint.

## Final Solution
Tested the upload independently with Postman:

```text
HTTP Method: PUT
Body: Binary
File: PDF
```

Conceptual flow:

```text
Application → Backend
        │
        │ Request upload authorization
        ▼
Backend generates presigned PUT URL
        │
        ▼
Client / Browser
        │
        │ PUT PDF
        ▼
Private S3 Documents Bucket
```

## Engineering Lesson
When debugging a multi-layer integration, test layers independently before blaming the whole path.

---

# Case 9 — Postman Presigned URL Query Parameters

## Problem
AWS signing parameters appeared automatically in Postman's Params view after pasting the presigned URL, creating concern that Postman had modified the request.

## Root Cause
The signature parameters were already encoded in the URL query string. Postman only parsed and displayed them.

## Final Solution
The signing parameters were left unchanged and the request was sent using PUT with a binary PDF body.

## Engineering Lesson
Treat a presigned URL as a complete temporary authorization mechanism. Do not edit its signing parameters without a specific reason.

---

# Case 10 — IAM NoSuchEntity During Automation

## Services Involved
- AWS IAM
- Boto3

## Problem
The infrastructure script failed while attaching inline policies because referenced roles such as:

- `AppBackendRole`
- `TextractWorkerRole`
- `ComprehendWorkerRole`

did not yet exist.

Example error:

```text
botocore.errorfactory.NoSuchEntityException
The role with name AppBackendRole cannot be found.
```

## Root Cause
The script defined policy attachment logic before the required IAM role resources had been created.

## Final Solution
Role-policy attachment was temporarily skipped so the S3 infrastructure could deploy independently.

The correct dependency order was clarified:

```text
Create IAM Role
      ↓
Configure Trust Policy
      ↓
Define Permissions
      ↓
Attach Permissions
      ↓
AWS Service Assumes Role
```

## Engineering Lesson
IAM policies and IAM roles are separate resources. Automation must respect resource dependency order.

---

# Case 11 — IAM Identity Policy vs S3 Bucket Policy

## Services Involved
- AWS IAM
- Amazon S3

## Problem
There was confusion between permissions granted to an identity and permissions enforced directly on an S3 resource.

## Resolution

### IAM Identity Policy
Defines what an IAM identity is allowed to do.

Example:

```text
Backend Role
   ↓
IAM permissions
   ↓
PutObject
   ↓
documents/raw/
```

### S3 Bucket Policy
Attached directly to an S3 bucket and controls access to that resource.

For the website:

```text
CloudFront → OAC → S3 Website Bucket
                       │
                       └─ Bucket Policy allows CloudFront GetObject
```

## Engineering Lesson
Before writing policy JSON, ask:

1. Who needs permission?
2. Where should that permission be enforced?

---

# Case 12 — CloudFront OAC Bucket Policy Dependency / Placeholder Resolution

## Services Involved
- Amazon CloudFront
- Amazon S3

## Problem
Early S3 automation prepared a CloudFront bucket policy before the CloudFront distribution existed.

Temporary placeholder values were therefore used for the AWS account and distribution identifiers.

## Root Cause
The bucket policy depended on identifiers that were only available after the CloudFront resource was created.

## Historical Workaround
The policy structure was prepared first with placeholder values.

## Final Resolution
CloudFront OAC and the real distribution were later created, and the S3 bucket policy was updated to reference the actual CloudFront distribution `SourceArn`.

Final architecture:

```text
Internet
   │
 HTTPS
   ▼
CloudFront
   │
   ▼
OAC
   │
   ▼
Private S3 Website Bucket
```

## Engineering Lesson
A syntactically valid resource policy is not necessarily operational. Cross-resource dependencies must reference real deployed identifiers.

**Status: RESOLVED.**

---

# Case 13 — Cognito Authentication Architecture

## Service Involved
- Amazon Cognito

## Problem
The application required secure sign-up/sign-in without implementing password storage, verification, reset flows, and session security from scratch.

## Root Cause
Custom authentication would add unnecessary security and operational complexity to the MVP.

## Final Solution
Implemented:

- Amazon Cognito User Pool
- Cognito Hosted UI
- Email-based sign-in / verification
- OAuth 2.0 Authorization Code flow
- PKCE for the SPA

## Engineering Lesson
Managed identity services reduce the security burden and let the application focus on its core product logic.

---

# Final Phase 1 Architecture State

| Area | Final State |
|---|---|
| Website delivery | CloudFront + OAC + HTTPS → private `vb-website-2025` |
| Website S3 security | Block Public Access ON; ACLs disabled; SSE-S3 |
| Document storage | Private `vb-documents-2025`; SSE-S3; versioning enabled |
| Authentication | Cognito User Pool + Hosted UI + Authorization Code + PKCE |
| Uploads | Controlled presigned URL pattern; independently testable with Postman |
| Lifecycle | Retention rules applied to control storage growth and cost |
| CloudFront policy | Uses real deployed distribution identity; placeholder stage resolved |
| Phase status | Foundation operational and ready for later event-driven processing phases |

---

# Key Engineering Lessons from Phase 1

## 1. Dependency Management
AWS resources are not independent.

IAM roles must exist before policy attachment. CloudFront authorization must reference the deployed distribution. Presigned URLs require correctly scoped S3 permissions.

## 2. Troubleshooting by Isolation
Separate the browser, backend, IAM, and S3 layers.

Independent tests such as Postman can quickly narrow the fault domain.

## 3. Security by Default
Start with:

- Private buckets
- Block Public Access
- Disabled ACLs
- Encryption
- Controlled access paths
- Managed identity

## 4. Separation of Concerns
Website delivery, document storage, identity, and later processing workloads should have clear boundaries.

## 5. Avoid Unnecessary Complexity
Do not enable AWS services or controls simply because they exist.

Add them when they solve a concrete requirement.

---

## Phase 1 Troubleshooting Status

**ALL DOCUMENTED PHASE 1 CASES: RESOLVED ✅**
