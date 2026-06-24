data "aws_caller_identity" "current" {}

locals {
  dynamodb_table_suffixes = ["run-state", "anomaly", "routing-state", "containment-audit", "dashboard-views", "account-policy"]
  dynamodb_table_arns = [
    for suffix in local.dynamodb_table_suffixes :
    "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.project_name}-${var.environment}-${suffix}"
  ]

  dynamodb_table_names = {
    run_state       = "${var.project_name}-${var.environment}-run-state"
    anomaly         = "${var.project_name}-${var.environment}-anomaly"
    routing_state   = "${var.project_name}-${var.environment}-routing-state"
    audit           = "${var.project_name}-${var.environment}-containment-audit"
    dashboard_views = "${var.project_name}-${var.environment}-dashboard-views"
    account_policy  = "${var.project_name}-${var.environment}-account-policy"
  }
}

# 1. Networking Module
module "networking" {
  source = "../../modules/networking"

  project_name               = var.project_name
  environment                = var.environment
  aws_region                 = var.aws_region
  vpc_cidr_block             = "10.10.0.0/16"
  public_subnet_cidr_blocks  = ["10.10.1.0/24", "10.10.2.0/24"]
  private_subnet_cidr_blocks = ["10.10.10.0/24", "10.10.11.0/24"]
  availability_zones         = ["${var.aws_region}a", "${var.aws_region}b"]
  single_nat_gateway         = true
  tags                       = var.tags
}

# 2. Lakehouse Module
module "lakehouse" {
  source = "../../modules/lakehouse"

  project_name         = var.project_name
  environment          = var.environment
  aws_region           = var.aws_region
  audit_retention_days = 90
  tags                 = var.tags
}

# 3. Alerting Module
module "alerting" {
  source = "../../modules/alerting"

  project_name    = var.project_name
  environment     = var.environment
  sns_kms_key_arn = module.lakehouse.data_kms_key_arn
  tags            = var.tags
}

# 4. Secrets Manager secret for AI Engine auth
resource "aws_secretsmanager_secret" "ai_engine" {
  name                    = "${var.project_name}-${var.environment}-ai-engine-auth"
  recovery_window_in_days = 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "ai_engine" {
  secret_id = aws_secretsmanager_secret.ai_engine.id
  secret_string = jsonencode({
    endpoint_url = "http://${var.project_name}-eks-ai-engine-service.ai-engine.svc.cluster.local"
    token        = "dummy-token-placeholder"
  })
}

# 5. IAM Module
module "iam" {
  source = "../../modules/iam"

  project_name              = var.project_name
  environment               = var.environment
  lakehouse_bucket_arn      = module.lakehouse.lakehouse_bucket_arn
  audit_bucket_arn          = module.lakehouse.audit_bucket_arn
  dynamodb_table_arns       = local.dynamodb_table_arns
  kms_key_arns              = [module.lakehouse.data_kms_key_arn, module.lakehouse.audit_kms_key_arn, module.lakehouse.ddb_kms_key_arn]
  ai_engine_secret_arn      = aws_secretsmanager_secret.ai_engine.arn
  containment_apply_enabled = true
  tags                      = var.tags
}

# 6. EKS Module (infrastructure only)
module "eks" {
  source = "../../modules/eks"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  tags               = var.tags
}

# 7. Compute Lambda Module
module "compute_lambda" {
  source = "../../modules/compute-lambda"

  project_name              = var.project_name
  environment               = var.environment
  private_subnet_ids        = module.networking.private_subnet_ids
  lambda_security_group_id  = module.networking.lambda_security_group_id
  lambda_role_arns          = module.iam.lambda_role_arns
  lakehouse_bucket_name     = module.lakehouse.lakehouse_bucket_name
  audit_bucket_name         = module.lakehouse.audit_bucket_name
  dynamodb_table_names      = local.dynamodb_table_names
  ai_engine_endpoint_url    = module.eks.ai_engine_internal_endpoint
  ai_engine_secret_name     = aws_secretsmanager_secret.ai_engine.name
  containment_apply_enabled = true
  log_retention_days        = 14
  tags                      = var.tags
}

# 8. Orchestration Module
module "orchestration" {
  source = "../../modules/orchestration"

  project_name                 = var.project_name
  environment                  = var.environment
  scheduler_expression         = "rate(24 hours)"
  step_functions_role_arn      = module.iam.step_functions_role_arn
  scheduler_role_arn           = module.iam.scheduler_role_arn
  lambda_function_arns         = module.compute_lambda.lambda_alias_arns
  ddb_kms_key_arn              = module.lakehouse.ddb_kms_key_arn
  audit_bucket_name            = module.lakehouse.audit_bucket_name
  finance_alerts_topic_arn     = module.alerting.finance_topic_arn
  engineering_alerts_topic_arn = module.alerting.engineering_topic_arn
  tags                         = var.tags
}

# 9. Observability Module
module "observability" {
  source = "../../modules/observability"

  project_name          = var.project_name
  environment           = var.environment
  state_machine_arn     = module.orchestration.state_machine_arn
  lambda_function_names = values(module.compute_lambda.lambda_function_names)
  engineering_topic_arn = module.alerting.engineering_topic_arn
  finance_topic_arn     = module.alerting.finance_topic_arn
  log_retention_days    = 14
  tags                  = var.tags
}

# 10. Dashboard Module
module "dashboard" {
  source = "../../modules/dashboard"

  project_name          = var.project_name
  environment           = var.environment
  glue_database_name    = module.lakehouse.glue_database_name
  athena_workgroup_name = module.lakehouse.athena_workgroup_name
  enable_quicksight     = false
  tags                  = var.tags
}
