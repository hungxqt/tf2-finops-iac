# CUR 2.0 / AWS Data Exports must be created in the source billing account.
# Call this module with a provider configured for that account, usually us-east-1.

locals {
  base_table_config = {
    INCLUDE_CAPACITY_RESERVATION_DATA     = "TRUE"
    INCLUDE_IAM_PRINCIPAL_DATA            = "TRUE"
    INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY = "FALSE"
    INCLUDE_RESOURCES                     = "TRUE"
    INCLUDE_SPLIT_COST_ALLOCATION_DATA    = var.include_split_cost_allocation_data ? "TRUE" : "FALSE"
    TIME_GRANULARITY                      = var.time_granularity
  }

  cost_and_usage_report_config = var.billing_view_arn != "" ? merge(local.base_table_config, {
    BILLING_VIEW_ARN = var.billing_view_arn
  }) : local.base_table_config

  query_statement = join(" ", [
    "SELECT",
    "bill_billing_period_start_date,",
    "bill_payer_account_id,",
    "line_item_usage_account_id,",
    "line_item_usage_account_name,",
    "line_item_line_item_type,",
    "line_item_usage_start_date,",
    "line_item_usage_end_date,",
    "line_item_product_code,",
    "line_item_usage_type,",
    "line_item_operation,",
    "line_item_resource_id,",
    "line_item_usage_amount,",
    "pricing_unit,",
    "line_item_unblended_rate,",
    "line_item_unblended_cost,",
    "line_item_currency_code,",
    "product.product_name AS product_product_name,",
    "product.region_code AS product_region_code,",
    "product.instance_type AS product_instance_type,",
    "resource_tags.user_team AS resource_tags_user_team,",
    "resource_tags.user_environment AS resource_tags_user_environment,",
    "resource_tags.user_cost_center AS resource_tags_user_cost_center,",
    "resource_tags.user_owner AS resource_tags_user_owner",
    "FROM COST_AND_USAGE_REPORT"
  ])
}

resource "aws_bcmdataexports_export" "cur" {
  export {
    name        = var.export_name
    description = var.description

    data_query {
      query_statement = local.query_statement
      table_configurations = {
        COST_AND_USAGE_REPORT = local.cost_and_usage_report_config
      }
    }

    destination_configurations {
      s3_destination {
        s3_bucket = var.destination_bucket_name
        s3_prefix = trim(var.destination_prefix, "/")
        s3_region = var.destination_region

        s3_output_configurations {
          output_type = "CUSTOM"
          format      = "PARQUET"
          compression = "PARQUET"
          overwrite   = var.overwrite
        }
      }
    }

    refresh_cadence {
      frequency = "SYNCHRONOUS"
    }
  }

  tags = var.tags
}
