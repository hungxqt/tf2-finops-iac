# Khanh GitOps Guide

This guide describes the parallel GitOps workflow implemented by the `khanh-*` GitHub Actions files. It does not replace the existing workflows.

## 1. Files

- `.github/workflows/khanh-terraform-ci.yml`: validates pull requests.
- `.github/workflows/khanh-terraform-apply.yml`: creates a Terraform plan, uploads it as an artifact, then applies that reviewed plan.
- `.github/workflows/khanh-drift-detection.yml`: runs scheduled drift checks and opens a GitHub issue when AWS differs from Git.

## 2. Required GitHub Variables

Configure these repository or organization variables before running the workflows:

```text
KHANH_AWS_ROLE_TO_ASSUME
KHANH_SANDBOX_REQUEST_IMAGE_URI
KHANH_SANDBOX_WORKER_IMAGE_URI
KHANH_SANDBOX_ALB_CERTIFICATE_ARN
KHANH_SANDBOX_CLOUDFRONT_ACM_CERTIFICATE_ARN
KHANH_SANDBOX_CLOUDFRONT_ALIASES_JSON
KHANH_STAGING_REQUEST_IMAGE_URI
KHANH_STAGING_WORKER_IMAGE_URI
KHANH_STAGING_ALB_CERTIFICATE_ARN
KHANH_STAGING_CLOUDFRONT_ACM_CERTIFICATE_ARN
KHANH_STAGING_CLOUDFRONT_ALIASES_JSON
KHANH_PROD_REQUEST_IMAGE_URI
KHANH_PROD_WORKER_IMAGE_URI
KHANH_PROD_ALB_CERTIFICATE_ARN
KHANH_PROD_CLOUDFRONT_ACM_CERTIFICATE_ARN
KHANH_PROD_CLOUDFRONT_ALIASES_JSON
```

Optional variables:

```text
KHANH_SANDBOX_PRIVATE_HOSTED_ZONE_ID
KHANH_SANDBOX_PRIVATE_DNS_NAME
KHANH_STAGING_PRIVATE_HOSTED_ZONE_ID
KHANH_STAGING_PRIVATE_DNS_NAME
KHANH_PROD_PRIVATE_HOSTED_ZONE_ID
KHANH_PROD_PRIVATE_DNS_NAME
```

`KHANH_AWS_ROLE_TO_ASSUME` may be stored as a repository secret instead of a variable.

`KHANH_*_CLOUDFRONT_ALIASES_JSON` must be valid JSON, for example:

```json
["dashboard.sandbox.example.com"]
```

Image URI values must be digest-pinned:

```text
123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2-finops-sandbox-ai-request@sha256:<64-hex>
```

## 3. Branch Mapping

```text
develop -> sandbox
main    -> staging
manual workflow_dispatch -> sandbox, staging, or prod
```

Production is intentionally manual. Configure the GitHub `prod` environment with required reviewers.

## 4. How To Use

Open a pull request into `develop` or `main`. The CI workflow validates Terraform, packages Lambda code, runs Lambda tests, and performs security scans.

Merge to `develop` to deploy sandbox. Merge to `main` to deploy staging. The apply workflow creates a plan artifact and then applies that same artifact after the GitHub Environment gate.

Run production from the `Khanh GitOps Apply` workflow manually and select `prod`.

## 5. Drift Detection

The drift workflow runs daily for sandbox, staging, and prod. If `terraform plan -detailed-exitcode` returns `2`, the workflow opens a GitHub issue. It never auto-applies drift.

## 6. Current Caveat

The existing repository currently has a Terraform formatting issue in `modules/lakehouse/lakehouse.tftest.hcl`. The Khanh CI workflow keeps `terraform fmt -check -recursive` as a hard gate, so that file must be formatted before the new CI can pass.
