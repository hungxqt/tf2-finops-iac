# AI Wrapper Build Module

This module provisions a CodeBuild project to build and publish the AI Engine wrapper image. The wrapper copies AWS Lambda Web Adapter into the upstream FastAPI container and exposes it on port 8080.

## Features
- Pinned digest verification for upstream images.
- Rebuild-skipping using deterministic image tags.
- SSM Parameter Store integration to record build results.
- Least-privilege IAM configuration.
