name: "Khanh GitOps Drift Detection"

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:
    inputs:
      environment:
        description: "Environment to check"
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
  issues: write

jobs:
  select-environments:
    name: "Select drift targets"
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.select.outputs.matrix }}
    steps:
      - name: Select environments
        id: select
        shell: bash
        run: |
          set -euo pipefail
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo 'matrix={"environment":["${{ inputs.environment }}"]}' >> "$GITHUB_OUTPUT"
          else
            echo 'matrix={"environment":["sandbox","staging","prod"]}' >> "$GITHUB_OUTPUT"
          fi

  detect-drift:
    name: "Detect drift in ${{ matrix.environment }}"
    needs: select-environments
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix: ${{ fromJson(needs.select-environments.outputs.matrix) }}
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
          env_name="${{ matrix.environment }}"
          env_upper="$(echo "${env_name}" | tr '[:lower:]' '[:upper:]')"
          root="environments/${env_name}"

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

          payload = {
              "aws_region": "ap-southeast-1",
              "project_name": "tf2-finops",
              "environment": env_name,
              "request_image_uri": require(f"KHANH_{env_upper}_REQUEST_IMAGE_URI"),
              "worker_image_uri": require(f"KHANH_{env_upper}_WORKER_IMAGE_URI"),
              "replica_region": "ap-southeast-2",
              "cloudfront_acm_certificate_arn": require(f"KHANH_{env_upper}_CLOUDFRONT_ACM_CERTIFICATE_ARN"),
              "cloudfront_aliases": json.loads(require(f"KHANH_{env_upper}_CLOUDFRONT_ALIASES_JSON")),
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
          GITOPS_ENVIRONMENT: ${{ matrix.environment }}
          GITOPS_ENV_UPPER: ${{ matrix.environment == 'sandbox' && 'SANDBOX' || matrix.environment == 'staging' && 'STAGING' || 'PROD' }}
          GITOPS_ROOT: environments/${{ matrix.environment }}

      - name: Terraform init
        run: terraform -chdir="environments/${{ matrix.environment }}" init

      - name: Terraform drift plan
        id: drift
        shell: bash
        continue-on-error: true
        run: |
          set +e
          terraform -chdir="environments/${{ matrix.environment }}" plan -detailed-exitcode -out="khanh-drift-${{ matrix.environment }}.tfplan"
          code=$?
          echo "exitcode=${code}" >> "$GITHUB_OUTPUT"
          exit 0

      - name: Create drift issue
        if: steps.drift.outputs.exitcode == '2'
        uses: actions/github-script@v7
        with:
          script: |
            const environment = "${{ matrix.environment }}";
            const title = `Terraform drift detected in ${environment}`;
            const body = [
              `Drift detection found that AWS does not match Git for \`${environment}\`.`,
              "",
              `Workflow run: ${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`,
              "",
              "Do not auto-apply this drift. Review the plan, decide whether to import/revert/manual-fix, then make the matching change through Git."
            ].join("\n");
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title,
              body,
              labels: ["terraform", "drift", environment]
            });

      - name: Fail on Terraform error
        if: steps.drift.outputs.exitcode == '1'
        run: exit 1
