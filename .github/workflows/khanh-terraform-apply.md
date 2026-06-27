name: "Khanh GitOps Apply"

on:
  push:
    branches:
      - develop
      - main
    paths:
      - ".github/workflows/khanh-*.yml"
      - "environments/**"
      - "lambda_src/**"
      - "modules/**"
      - "scripts/**"
      - ".terraform-version"
      - ".tflint.hcl"
      - "Makefile"
  workflow_dispatch:
    inputs:
      environment:
        description: "Environment to deploy"
        required: true
        default: "sandbox"
        type: choice
        options:
          - sandbox
          - staging
          - prod

permissions:
  contents: read
  id-token: write

jobs:
  select-environment:
    name: "Select GitOps target"
    runs-on: ubuntu-latest
    outputs:
      environment: ${{ steps.select.outputs.environment }}
      env_upper: ${{ steps.select.outputs.env_upper }}
      root: ${{ steps.select.outputs.root }}
    steps:
      - name: Select environment
        id: select
        shell: bash
        run: |
          set -euo pipefail

          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            target="${{ inputs.environment }}"
          elif [ "${{ github.ref_name }}" = "develop" ]; then
            target="sandbox"
          elif [ "${{ github.ref_name }}" = "main" ]; then
            target="staging"
          else
            echo "Unsupported branch: ${{ github.ref_name }}" >&2
            exit 1
          fi

          echo "environment=${target}" >> "$GITHUB_OUTPUT"
          echo "env_upper=$(echo "${target}" | tr '[:lower:]' '[:upper:]')" >> "$GITHUB_OUTPUT"
          echo "root=environments/${target}" >> "$GITHUB_OUTPUT"

  plan:
    name: "Create reviewed Terraform plan"
    needs: select-environment
    runs-on: ubuntu-latest
    env:
      AWS_REGION: ap-southeast-1
      TF_IN_AUTOMATION: "true"
      KHANH_SANDBOX_REQUEST_IMAGE_URI: ${{ vars.KHANH_SANDBOX_REQUEST_IMAGE_URI }}
      KHANH_SANDBOX_WORKER_IMAGE_URI: ${{ vars.KHANH_SANDBOX_WORKER_IMAGE_URI }}
      KHANH_SANDBOX_ALB_CERTIFICATE_ARN: ${{ vars.KHANH_SANDBOX_ALB_CERTIFICATE_ARN }}
      KHANH_SANDBOX_CLOUDFRONT_ACM_CERTIFICATE_ARN: ${{ vars.KHANH_SANDBOX_CLOUDFRONT_ACM_CERTIFICATE_ARN }}
      KHANH_SANDBOX_CLOUDFRONT_ALIASES_JSON: ${{ vars.KHANH_SANDBOX_CLOUDFRONT_ALIASES_JSON }}
      KHANH_SANDBOX_PRIVATE_HOSTED_ZONE_ID: ${{ vars.KHANH_SANDBOX_PRIVATE_HOSTED_ZONE_ID }}
      KHANH_SANDBOX_PRIVATE_DNS_NAME: ${{ vars.KHANH_SANDBOX_PRIVATE_DNS_NAME }}
      KHANH_STAGING_REQUEST_IMAGE_URI: ${{ vars.KHANH_STAGING_REQUEST_IMAGE_URI }}
      KHANH_STAGING_WORKER_IMAGE_URI: ${{ vars.KHANH_STAGING_WORKER_IMAGE_URI }}
      KHANH_STAGING_ALB_CERTIFICATE_ARN: ${{ vars.KHANH_STAGING_ALB_CERTIFICATE_ARN }}
      KHANH_STAGING_CLOUDFRONT_ACM_CERTIFICATE_ARN: ${{ vars.KHANH_STAGING_CLOUDFRONT_ACM_CERTIFICATE_ARN }}
      KHANH_STAGING_CLOUDFRONT_ALIASES_JSON: ${{ vars.KHANH_STAGING_CLOUDFRONT_ALIASES_JSON }}
      KHANH_STAGING_PRIVATE_HOSTED_ZONE_ID: ${{ vars.KHANH_STAGING_PRIVATE_HOSTED_ZONE_ID }}
      KHANH_STAGING_PRIVATE_DNS_NAME: ${{ vars.KHANH_STAGING_PRIVATE_DNS_NAME }}
      KHANH_PROD_REQUEST_IMAGE_URI: ${{ vars.KHANH_PROD_REQUEST_IMAGE_URI }}
      KHANH_PROD_WORKER_IMAGE_URI: ${{ vars.KHANH_PROD_WORKER_IMAGE_URI }}
      KHANH_PROD_ALB_CERTIFICATE_ARN: ${{ vars.KHANH_PROD_ALB_CERTIFICATE_ARN }}
      KHANH_PROD_CLOUDFRONT_ACM_CERTIFICATE_ARN: ${{ vars.KHANH_PROD_CLOUDFRONT_ACM_CERTIFICATE_ARN }}
      KHANH_PROD_CLOUDFRONT_ALIASES_JSON: ${{ vars.KHANH_PROD_CLOUDFRONT_ALIASES_JSON }}
      KHANH_PROD_PRIVATE_HOSTED_ZONE_ID: ${{ vars.KHANH_PROD_PRIVATE_HOSTED_ZONE_ID }}
      KHANH_PROD_PRIVATE_DNS_NAME: ${{ vars.KHANH_PROD_PRIVATE_DNS_NAME }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.15.6"

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Configure AWS credentials with GitHub OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.KHANH_AWS_ROLE_TO_ASSUME || vars.KHANH_AWS_ROLE_TO_ASSUME }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Package Lambda zips
        shell: pwsh
        run: ./scripts/package-lambdas.ps1

      - name: Write GitOps tfvars
        shell: bash
        run: |
          set -euo pipefail

          env_upper="${{ needs.select-environment.outputs.env_upper }}"
          root="${{ needs.select-environment.outputs.root }}"

          request_var="KHANH_${env_upper}_REQUEST_IMAGE_URI"
          worker_var="KHANH_${env_upper}_WORKER_IMAGE_URI"
          alb_cert_var="KHANH_${env_upper}_ALB_CERTIFICATE_ARN"
          cloudfront_cert_var="KHANH_${env_upper}_CLOUDFRONT_ACM_CERTIFICATE_ARN"
          aliases_var="KHANH_${env_upper}_CLOUDFRONT_ALIASES_JSON"
          hosted_zone_var="KHANH_${env_upper}_PRIVATE_HOSTED_ZONE_ID"
          dns_name_var="KHANH_${env_upper}_PRIVATE_DNS_NAME"

          : "${!request_var:?Missing ${request_var} GitHub variable}"
          : "${!worker_var:?Missing ${worker_var} GitHub variable}"
          : "${!alb_cert_var:?Missing ${alb_cert_var} GitHub variable}"
          : "${!cloudfront_cert_var:?Missing ${cloudfront_cert_var} GitHub variable}"
          : "${!aliases_var:?Missing ${aliases_var} GitHub variable, for example [\"dashboard.example.com\"]}"

          python - <<'PY'
          import json
          import os
          from pathlib import Path

          env_name = os.environ["GITOPS_ENVIRONMENT"]
          env_upper = os.environ["GITOPS_ENV_UPPER"]
          root = Path(os.environ["GITOPS_ROOT"])

          def require(name):
              value = os.environ.get(name, "")
              if not value:
                  raise SystemExit(f"Missing GitHub variable: {name}")
              return value

          def optional(name, default=""):
              return os.environ.get(name, default)

          aliases = json.loads(require(f"KHANH_{env_upper}_CLOUDFRONT_ALIASES_JSON"))
          payload = {
              "aws_region": "ap-southeast-1",
              "project_name": "tf2-finops",
              "environment": env_name,
              "request_image_uri": require(f"KHANH_{env_upper}_REQUEST_IMAGE_URI"),
              "worker_image_uri": require(f"KHANH_{env_upper}_WORKER_IMAGE_URI"),
              "replica_region": "ap-southeast-2",
              "cloudfront_acm_certificate_arn": require(f"KHANH_{env_upper}_CLOUDFRONT_ACM_CERTIFICATE_ARN"),
              "cloudfront_aliases": aliases,
              "dashboard_geo_restriction_type": "blacklist",
              "dashboard_geo_restriction_locations": ["CU", "IR", "KP", "SY"],
              "alb_certificate_arn": require(f"KHANH_{env_upper}_ALB_CERTIFICATE_ARN"),
              "private_hosted_zone_id": optional(f"KHANH_{env_upper}_PRIVATE_HOSTED_ZONE_ID"),
              "private_dns_name": optional(f"KHANH_{env_upper}_PRIVATE_DNS_NAME"),
              "sigv4_service_name": "ai-engine",
              "destroyable": env_name == "sandbox",
              "tags": {
                  "Environment": env_name,
                  "Project": "tf2-finops",
                  "ManagedBy": "Terraform",
                  "GitOpsFlow": "khanh"
              }
          }

          root.joinpath("khanh.auto.tfvars.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
          PY
        env:
          GITOPS_ENVIRONMENT: ${{ needs.select-environment.outputs.environment }}
          GITOPS_ENV_UPPER: ${{ needs.select-environment.outputs.env_upper }}
          GITOPS_ROOT: ${{ needs.select-environment.outputs.root }}

      - name: Terraform format check
        run: terraform fmt -check -recursive

      - name: Terraform init
        run: terraform -chdir="${{ needs.select-environment.outputs.root }}" init

      - name: Terraform validate
        run: terraform -chdir="${{ needs.select-environment.outputs.root }}" validate

      - name: Terraform plan
        run: terraform -chdir="${{ needs.select-environment.outputs.root }}" plan -out="khanh-${{ needs.select-environment.outputs.environment }}.tfplan"

      - name: Upload reviewed plan artifact
        uses: actions/upload-artifact@v4
        with:
          name: khanh-${{ needs.select-environment.outputs.environment }}-tfplan
          path: ${{ needs.select-environment.outputs.root }}/khanh-${{ needs.select-environment.outputs.environment }}.tfplan
          retention-days: 7
          if-no-files-found: error

      - name: Upload Lambda package artifact
        uses: actions/upload-artifact@v4
        with:
          name: khanh-lambda-packages-${{ needs.select-environment.outputs.environment }}
          path: .build/lambda/*.zip
          retention-days: 7
          if-no-files-found: error

  apply:
    name: "Apply reviewed Terraform plan"
    needs:
      - select-environment
      - plan
    runs-on: ubuntu-latest
    environment: ${{ needs.select-environment.outputs.environment }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.15.6"

      - name: Configure AWS credentials with GitHub OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.KHANH_AWS_ROLE_TO_ASSUME || vars.KHANH_AWS_ROLE_TO_ASSUME }}
          aws-region: ap-southeast-1

      - name: Download reviewed plan artifact
        uses: actions/download-artifact@v4
        with:
          name: khanh-${{ needs.select-environment.outputs.environment }}-tfplan
          path: ${{ needs.select-environment.outputs.root }}

      - name: Download Lambda package artifact
        uses: actions/download-artifact@v4
        with:
          name: khanh-lambda-packages-${{ needs.select-environment.outputs.environment }}
          path: .build/lambda

      - name: Terraform init
        run: terraform -chdir="${{ needs.select-environment.outputs.root }}" init

      - name: Terraform apply reviewed plan
        run: terraform -chdir="${{ needs.select-environment.outputs.root }}" apply -auto-approve "khanh-${{ needs.select-environment.outputs.environment }}.tfplan"




