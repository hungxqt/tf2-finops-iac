# Terraform Test for Lakehouse Module Glue Table Configurations

variables {
  project_name                 = "tf2-finops"
  environment                  = "sandbox"
  aws_region                   = "ap-southeast-1"
  lakehouse_replica_bucket_arn = "arn:aws:s3:::tf2-finops-sandbox-lakehouse-replica"
  audit_replica_bucket_arn     = "arn:aws:s3:::tf2-finops-sandbox-audit-replica"
  athena_replica_bucket_arn    = "arn:aws:s3:::tf2-finops-sandbox-athena-replica"
  destroyable                  = true
}

run "validate_glue_catalog_tables" {
  command = plan

  assert {
    condition     = aws_glue_catalog_table.cur_data.name == "cur_data"
    error_message = "The curated cost data table name must be 'cur_data'"
  }

  assert {
    condition     = aws_glue_catalog_table.cur_data.partition_keys[0].name == "account_id"
    error_message = "The first partition key of curated cost table must be 'account_id'"
  }

  assert {
    condition     = aws_glue_catalog_table.cur_data.partition_keys[1].name == "year"
    error_message = "The second partition key of curated cost table must be 'year'"
  }

  assert {
    condition     = aws_glue_catalog_table.cur_data.partition_keys[2].name == "month"
    error_message = "The third partition key of curated cost table must be 'month'"
  }

  assert {
    condition     = aws_glue_catalog_table.cur_data.storage_descriptor[0].input_format == "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    error_message = "The input format of curated cost table must be Parquet MapredParquetInputFormat"
  }

  assert {
    condition     = aws_glue_catalog_table.cur_data.storage_descriptor[0].output_format == "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    error_message = "The output format of curated cost table must be Parquet MapredParquetOutputFormat"
  }

  assert {
    condition     = aws_glue_catalog_table.containment_audit.name == "containment_audit"
    error_message = "The containment audit table name must be 'containment_audit'"
  }

  assert {
    condition     = aws_glue_catalog_table.containment_audit.partition_keys[0].name == "account_id"
    error_message = "The first partition key of containment audit table must be 'account_id'"
  }

  assert {
    condition     = aws_glue_catalog_table.containment_audit.partition_keys[1].name == "year"
    error_message = "The second partition key of containment audit table must be 'year'"
  }

  assert {
    condition     = aws_glue_catalog_table.containment_audit.partition_keys[2].name == "month"
    error_message = "The third partition key of containment audit table must be 'month'"
  }

  assert {
    condition     = aws_glue_catalog_table.containment_audit.storage_descriptor[0].input_format == "org.apache.hadoop.mapred.TextInputFormat"
    error_message = "The input format of containment audit table must be JSON TextInputFormat"
  }

  assert {
    condition     = aws_glue_catalog_table.containment_audit.storage_descriptor[0].output_format == "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    error_message = "The output format of containment audit table must be JSON HiveIgnoreKeyTextOutputFormat"
  }
}

run "validate_cur_export_policy_with_members" {
  command = plan

  variables {
    create_cur_export_bucket     = true
    telemetry_member_account_ids = ["111111111111", "222222222222"]
    cur_export_name              = "memberCUR"
  }

  assert {
    condition     = contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Resource, "arn:aws:s3:::tf2-finops-cur-export-bucket/111111111111/memberCUR/*") && contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Resource, "arn:aws:s3:::tf2-finops-cur-export-bucket/222222222222/memberCUR/*")
    error_message = "Resource list must contain both member-account CUR prefixes"
  }

  assert {
    condition     = contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Condition.StringEquals["aws:SourceAccount"], "111111111111") && contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Condition.StringEquals["aws:SourceAccount"], "222222222222")
    error_message = "aws:SourceAccount condition must contain both member accounts"
  }

  assert {
    condition     = contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Condition.StringLike["aws:SourceArn"], "arn:aws:bcm-data-exports:us-east-1:111111111111:export/*") && contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Condition.StringLike["aws:SourceArn"], "arn:aws:bcm-data-exports:us-east-1:222222222222:export/*")
    error_message = "aws:SourceArn condition must contain both member-account CUR export ARNs"
  }

  assert {
    condition     = !contains(jsondecode(data.aws_iam_policy_document.cur_export[0].json).Statement[1].Condition.StringEquals["aws:SourceAccount"], data.aws_caller_identity.current.account_id)
    error_message = "aws:SourceAccount must not contain caller account ID when member accounts are configured"
  }
}
