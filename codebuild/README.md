# Shared CodeBuild Root for AI Wrapper Image Publishing

This Terraform root manages the single shared CodeBuild wrapper-image publisher and ECR repository.

## Deployment Flow
1. **Bootstrap**: Run initial `bootstrap` to set up remote state.
2. **CodeBuild Setup**: Apply this `codebuild/` root to provision the shared ECR repository and CodeBuild project:
   ```powershell
   cd codebuild
   terraform init
   terraform apply
   ```
3. **Trigger Build**: Trigger the manual CodeBuild project with the digest-pinned AIOps upstream image:
   ```bash
   aws codebuild start-build \
     --project-name tf2-finops-ai-wrapper-build \
     --environment-variables-override name=UPSTREAM_IMAGE_URI,value=<upstream-digest-uri>,type=PLAINTEXT
   ```
4. **Environment Deployment**: Retrieve the wrapped image URI from SSM Parameter Store at `/tf2-finops/shared/ai-wrapper/latest-image-uri`, and pass it to the sandbox, staging, or prod environment deployment as `request_image_uri`.
