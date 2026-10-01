# Vocabulary Builder MVP

## Phase 1 — Engineering Troubleshooting Report

**Phase:** AWS Foundation  
**Status:** ✅ Resolved

---

## Overview

Phase 1 focused on building the secure AWS foundation of the Vocabulary Builder before introducing AI processing services.

The main engineering areas included:

- Secure website hosting
- User authentication
- Private document storage
- Infrastructure preparation
- Cost optimization
- AWS security best practices

During implementation, several architecture and configuration challenges were encountered.

This document records the problems, root causes, solutions, and engineering lessons learned.

---

# Case 1 — CloudFront + OAC + Private S3 Access

## Services Involved

- Amazon S3
- Amazon CloudFront
- Origin Access Control (OAC)

## Problem

The website needed to remain publicly accessible while the S3 website bucket remained completely private.

After enabling **S3 Block Public Access**, the website stopped loading correctly.

## Symptoms

- Website became inaccessible.
- CloudFront returned `Access Denied`.
- S3 objects could no longer be accessed through the existing configuration.

## Troubleshooting Attempts

### Attempt 1 — Public S3 Bucket

Making the S3 bucket public allowed the website to work.

However, this violated the project's security requirements.

### Attempt 2 — Public ACLs

Public-read ACL permissions also allowed access.

However, this approach did not align with the desired AWS security model.

## Root Cause

CloudFront did not have permission to retrieve objects from the private S3 bucket.

Making S3 private was correct, but a trusted access path between CloudFront and S3 had not yet been configured.

## Final Solution

Implemented:

- CloudFront Origin Access Control (OAC)
- SigV4 request signing
- S3 bucket policy allowing CloudFront access

Final request path:

```text
User
  │
  ▼
CloudFront
  │
  ▼
OAC
SigV4 Signed Request
  │
  ▼
Private S3 Bucket
```

## Result

The website remained publicly available through CloudFront while the S3 bucket remained private.

## Engineering Lesson

A public website does not require a public S3 bucket.

The architecture used:

```text
Private S3
    +
CloudFront
    +
OAC
```

This provided public website delivery without directly exposing the storage layer.

---

# Case 2 — BucketOwnerEnforced Migration

## Service Involved

- Amazon S3

## Problem

S3 permissions became harder to reason about when multiple authorization mechanisms were involved.

These included:

- ACLs
- IAM policies
- Bucket policies

## Root Cause

Using multiple permission models simultaneously increases configuration complexity and can create permission conflicts.

## Final Solution

Enabled:

```text
BucketOwnerEnforced
```

This disabled ACLs completely.

Permissions could then be controlled using:

- IAM policies
- S3 bucket policies

## Result

The authorization model became simpler and easier to troubleshoot.

## Engineering Lesson

Reducing the number of authorization layers simplifies both security management and troubleshooting.

---

# Case 3 — Single Bucket vs Two-Bucket Architecture

## Service Involved

- Amazon S3

## Problem

An architectural decision was required:

Should website files and uploaded user documents use the same S3 bucket?

## Initial Option

A single bucket could have contained:

```text
website/
documents/
outputs/
```

## Risks Identified

A permissions mistake could potentially expose:

- User PDFs
- OCR results
- AI-generated content

## Final Solution

The workloads were separated into two buckets.

### Website Bucket

```text
vb-website-2025
```

### Documents Bucket

```text
vb-documents-2025
```

## Result

Website content and private user data received separate security boundaries.

## Engineering Lesson

Workload isolation reduces both operational and security risk.

---

# Case 4 — Secure Document Storage

## Service Involved

- Amazon S3

## Problem

User-uploaded documents required secure storage while also remaining available to later processing stages.

## Security Controls Implemented

### Block Public Access

```text
Enabled
```

### Encryption

```text
SSE-S3
```

### Versioning

```text
Enabled
```

## Result

The documents bucket received a secure storage baseline with:

- Protection against public exposure
- Encryption at rest
- Protection against accidental object changes or deletion through versioning

## Engineering Lesson

Security controls should be part of the initial architecture rather than added after the application is built.

---

# Case 5 — Lifecycle Cost Optimization

## Service Involved

- Amazon S3

## Problem

Uploaded files and processing outputs could accumulate over time and continuously increase storage costs.

## Solution

S3 lifecycle policies were configured.

```text
raw/
→ Delete after 90 days

textract-output/
→ Delete after 730 days

comprehend-output/
→ Delete after 730 days
```

## Result

Temporary and processing data received defined retention periods instead of remaining in storage indefinitely.

## Engineering Lesson

Cost optimization is an architectural responsibility, not only an operational task performed after deployment.

---

# Case 6 — Cognito Authentication Architecture

## Service Involved

- Amazon Cognito

## Problem

The application required secure user authentication without creating and maintaining a custom identity system.

## Rejected Approach

Building custom authentication would require handling:

- Password storage
- Password hashing
- MFA
- Email verification
- Password reset flows
- Session management

## Final Solution

Implemented:

- Amazon Cognito User Pool
- Cognito Hosted UI
- OAuth 2.0 Authorization Code Flow
- PKCE

## Result

Authentication could be handled through an AWS-managed identity service instead of implementing password and identity management inside the application.

## Engineering Lesson

Managed identity services can significantly reduce the security and operational complexity of implementing authentication from scratch.

---

# Phase 1 Troubleshooting Results

The troubleshooting and architecture decisions resulted in:

- ✅ CloudFront operational
- ✅ HTTPS website delivery
- ✅ Private S3 website hosting
- ✅ CloudFront OAC configured
- ✅ Cognito authentication operational
- ✅ Secure document storage
- ✅ SSE-S3 encryption
- ✅ S3 versioning
- ✅ Lifecycle policies
- ✅ Infrastructure prepared for later processing stages

---

# Key Engineering Story

One of the most important Phase 1 challenges was serving a public website while keeping its S3 origin completely private.

Making the bucket private initially caused CloudFront access failures.

The problem was traced to the missing trusted access path between CloudFront and S3.

Origin Access Control (OAC) was introduced so CloudFront could send SigV4-signed requests to the private bucket.

The final architecture became:

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

This allowed the application to maintain public website availability without exposing the S3 bucket directly to the internet.

---

## Phase 1 Troubleshooting Status

**All documented Phase 1 cases: RESOLVED ✅**