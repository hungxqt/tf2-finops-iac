data "aws_caller_identity" "current" {}

resource "aws_athena_named_query" "spend_by_service" {
  name        = "${var.project_name}-${var.environment}-spend-by-service"
  workgroup   = var.athena_workgroup_name
  database    = var.glue_database_name
  description = "Total spend grouped by AWS service code for the past 30 days"
  query       = <<EOF
SELECT 
  line_item_product_code, 
  SUM(line_item_unblended_cost) AS total_cost
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -30, current_date)
GROUP BY line_item_product_code
ORDER BY total_cost DESC;
EOF
}

resource "aws_athena_named_query" "spend_by_account" {
  name        = "${var.project_name}-${var.environment}-spend-by-account"
  workgroup   = var.athena_workgroup_name
  database    = var.glue_database_name
  description = "Total spend grouped by AWS account for the past 30 days"
  query       = <<EOF
SELECT 
  line_item_usage_account_id, 
  SUM(line_item_unblended_cost) AS total_cost
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -30, current_date)
GROUP BY line_item_usage_account_id
ORDER BY total_cost DESC;
EOF
}

resource "aws_athena_named_query" "anomaly_spend_trends" {
  name        = "${var.project_name}-${var.environment}-anomaly-spend-trends"
  workgroup   = var.athena_workgroup_name
  database    = var.glue_database_name
  description = "Daily spend by service and account for the past 7 days"
  query       = <<EOF
SELECT 
  line_item_product_code, 
  line_item_usage_account_id, 
  SUM(line_item_unblended_cost) AS total_cost, 
  line_item_usage_start_date
FROM "${var.glue_database_name}"."cur_data"
WHERE line_item_usage_start_date >= date_add('day', -7, current_date)
GROUP BY line_item_product_code, line_item_usage_account_id, line_item_usage_start_date
ORDER BY line_item_usage_start_date DESC;
EOF
}

# Optional QuickSight infrastructure hooks (disabled by default under enable_quicksight = false)
resource "aws_quicksight_data_source" "athena" {
  count          = var.enable_quicksight ? 1 : 0
  data_source_id = "${var.project_name}-${var.environment}-athena-ds"
  name           = "${var.project_name}-${var.environment}-athena-ds"
  type           = "ATHENA"
  aws_account_id = data.aws_caller_identity.current.account_id

  parameters {
    athena {
      work_group = var.athena_workgroup_name
    }
  }
}
