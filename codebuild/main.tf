module "ai_wrapper_build" {
  source = "../modules/ai-wrapper-build"

  project_name                    = var.project_name
  environment                     = "shared"
  destroyable                     = var.destroyable
  aiops_source_ecr_repository_arn = var.aiops_source_ecr_repository_arn
  aiops_source_registry_id        = var.aiops_source_registry_id
  lambda_web_adapter_image        = var.lambda_web_adapter_image
  kms_key_arn                     = var.kms_key_arn
  tags                            = var.tags
}
