# TF2 FinOps IaC

This repository is the infrastructure-as-code home for **Task Force 2 - FinOps Watch**. Its purpose is to define and provision the AWS platform foundation that runs the FinOps cost ingestion, anomaly workflow integration, alerting, dashboard, containment guardrails, and audit trail.

## Purpose

Use this repo for cloud infrastructure that must be created before the FinOps Watch workloads can run. The expected scope includes:

- Terraform modules and environment roots for sandbox, staging, and production.
- Remote state, locking, and CI plan/apply controls.
- Cost-data platform resources such as CUR/Data Exports S3 buckets, raw and curated S3 zones, Glue Data Catalog, and Athena views.
- Scheduled workflow resources such as EventBridge Scheduler, Step Functions, Lambda workers, and DynamoDB run-state tables.
- Platform integrations for Finance and Engineering alert routing, dashboard data sources, containment audit records, and operational observability.
- Least-privilege IAM roles for read-only cost ingestion and tightly scoped non-prod containment actions.

## Repository Boundary

This repo owns AWS infrastructure definitions and deployment mechanics. It does not own:

- AI model code, anomaly detection internals, model training, or backtest implementation.
- Kubernetes or application desired-state manifests after the platform exists.
- Business documentation, except short operational notes needed to use the IaC.

Runtime deployment state belongs in `tf2-finops-gitops`. Architecture and delivery documentation belongs in `tf2-finops-docs`.

## FinOps Watch Guardrails

All infrastructure in this repo must preserve the client boundaries for FinOps Watch:

- AWS only.
- Synthetic data unless real billing access is explicitly provided.
- Dry-run first for containment.
- Audit records retained for at least 90 days.
- NEVER terminate prod, delete data, or modify IAM as an automated containment action.
