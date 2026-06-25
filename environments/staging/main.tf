data "aws_caller_identity" "current" {}

locals {
  dynamodb_table_suffixes = ["run-state", "anomaly", "routing-state", "containment-audit", "dashboard-views", "account-policy", "ai-results"]
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
    ai_results      = "${var.project_name}-${var.environment}-ai-results"
  }
}

# 1. Networking Module
module "networking" {
  source = "../../modules/networking"

  project_name               = var.project_name
  environment                = var.environment
  aws_region                 = var.aws_region
  vpc_cidr_block             = "10.20.0.0/16"
  public_subnet_cidr_blocks  = ["10.20.1.0/24", "10.20.2.0/24"]
  private_subnet_cidr_blocks = ["10.20.10.0/24", "10.20.11.0/24"]
  availability_zones         = ["${var.aws_region}a", "${var.aws_region}b"]
  single_nat_gateway         = false
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

# 4. IAM Module
module "iam" {
  source = "../../modules/iam"

  project_name              = var.project_name
  environment               = var.environment
  lakehouse_bucket_arn      = module.lakehouse.lakehouse_bucket_arn
  audit_bucket_arn          = module.lakehouse.audit_bucket_arn
  dynamodb_table_arns       = concat(local.dynamodb_table_arns, [module.orchestration.dynamodb_table_arns["error_budget"]])
  kms_key_arns              = [module.lakehouse.data_kms_key_arn, module.lakehouse.audit_kms_key_arn, module.lakehouse.ddb_kms_key_arn]
  ai_engine_secret_arn      = ""
  containment_apply_enabled = false
  queue_arns                = [module.orchestration.detection_queue_arn, module.orchestration.detection_dlq_arn, module.orchestration.rollback_status_queue_arn]
  tags                      = var.tags
}

# 5. ECS Fargate AI Engine Runtime
# 5. Lambda-based AI Engine Runtime
module "ai_runtime_lambda" {
  source = "../../modules/ai-runtime-lambda"

  project_name             = var.project_name
  environment              = var.environment
  aws_region               = var.aws_region
  private_subnet_ids       = module.networking.private_subnet_ids
  lambda_security_group_id = module.networking.lambda_security_group_id
  request_image_uri        = var.request_image_uri
  worker_image_uri         = var.worker_image_uri

  detect_queue_url   = module.orchestration.detection_queue_url
  detect_queue_arn   = module.orchestration.detection_queue_arn
  results_table_name = module.orchestration.dynamodb_table_names["ai_results"]
  results_table_arn  = module.orchestration.dynamodb_table_arns["ai_results"]

  curated_bucket_name  = module.lakehouse.lakehouse_bucket_name
  evidence_bucket_name = module.lakehouse.audit_bucket_name

  secret_arns  = []
  kms_key_arns = [module.lakehouse.data_kms_key_arn]
  tags         = var.tags
}

# 6. Compute Lambda Module
module "compute_lambda" {
  source = "../../modules/compute-lambda"

  project_name              = var.project_name
  environment               = var.environment
  aws_region                = var.aws_region
  private_subnet_ids        = module.networking.private_subnet_ids
  lambda_security_group_id  = module.networking.lambda_security_group_id
  lambda_role_arns          = module.iam.lambda_role_arns
  lakehouse_bucket_name     = module.lakehouse.lakehouse_bucket_name
  audit_bucket_name         = module.lakehouse.audit_bucket_name
  dynamodb_table_names      = merge(local.dynamodb_table_names, { error_budget = module.orchestration.dynamodb_table_names["error_budget"] })
  ai_engine_secret_name     = ""
  containment_apply_enabled = false
  log_retention_days        = 30
  tags                      = var.tags
}

# 7. Orchestration Module
module "orchestration" {
  source = "../../modules/orchestration"

  project_name            = var.project_name
  environment             = var.environment
  scheduler_expression    = "rate(24 hours)"
  step_functions_role_arn = module.iam.step_functions_role_arn
  scheduler_role_arn      = module.iam.scheduler_role_arn
  lambda_function_arns = merge(
    module.compute_lambda.lambda_alias_arns,
    {
      ai_request = module.ai_runtime_lambda.request_lambda_alias_arn
    }
  )
  ddb_kms_key_arn              = module.lakehouse.ddb_kms_key_arn
  sqs_kms_key_arn              = module.lakehouse.data_kms_key_arn
  audit_bucket_name            = module.lakehouse.audit_bucket_name
  finance_alerts_topic_arn     = module.alerting.finance_topic_arn
  engineering_alerts_topic_arn = module.alerting.engineering_topic_arn
  tags                         = var.tags
}

# 8. Observability Module
module "observability" {
  source = "../../modules/observability"

  project_name      = var.project_name
  environment       = var.environment
  state_machine_arn = module.orchestration.state_machine_arn
  lambda_function_names = concat(
    values(module.compute_lambda.lambda_function_names),
    [
      module.ai_runtime_lambda.request_lambda_function_name,
      module.ai_runtime_lambda.worker_lambda_function_name
    ]
  )
  engineering_topic_arn = module.alerting.engineering_topic_arn
  finance_topic_arn     = module.alerting.finance_topic_arn
  log_retention_days    = 30
  detection_queue_name  = "${var.project_name}-${var.environment}-detection-queue"
  detection_dlq_name    = "${var.project_name}-${var.environment}-detection-dlq"
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
  dashboard_kms_key_arn = module.lakehouse.data_kms_key_arn
  dashboard_data_prefix = "summaries/"
  tags                  = var.tags
}
