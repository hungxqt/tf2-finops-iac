-- Athena DDL Validation SQL Script
-- Use this script to validate or manually recreate the Glue tables with Partition Projection if needed.

-- 1. Create Database if not exists (usually managed by Terraform as "${project_name}_${environment}_database")
CREATE DATABASE IF NOT EXISTS tf2_finops_lakehouse_database;

-- 2. Create Curated Cost Data Table (Parquet Format)
CREATE EXTERNAL TABLE IF NOT EXISTS tf2_finops_lakehouse_database.cur_data (
    service string,
    region string,
    owner string,
    cost double,
    currency string,
    timestamp string,
    curated_at string,
    unblended_cost double,
    service_code string,
    resource_id string,
    squad string,
    cost_center string,
    schema_version string,
    correlation_id string,
    idempotency_key string,
    quality_score double
)
PARTITIONED BY (
    account_id string,
    year int,
    month int
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
STORED AS INPUTFORMAT 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION 's3://<lakehouse-bucket-name>/cost/curated/'
TBLPROPERTIES (
    'classification' = 'parquet',
    'projection.enabled' = 'true',
    'projection.account_id.type' = 'injected',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2035',
    'projection.month.type' = 'integer',
    'projection.month.range' = '1,12',
    'projection.month.digits' = '2',
    'storage.location.template' = 's3://<lakehouse-bucket-name>/cost/curated/account_id=${account_id}/year=${year}/month=${month}/'
);

-- 3. Create Containment Audit Table (JSON Format)
CREATE EXTERNAL TABLE IF NOT EXISTS tf2_finops_lakehouse_database.containment_audit (
    audit_id string,
    audit_uri string,
    audit_type string,
    actor string,
    timestamp string,
    correlation_id string,
    idempotency_key string,
    anomaly_id string,
    target_owner string,
    before_state string,
    proposed_after_state string,
    applied_after_state string,
    execution_mode string,
    rollback_path string,
    approval_status string,
    retention_location string,
    retention_period string,
    account_id string,
    resource_id string,
    owner string,
    audit_score double,
    numeric_audit_score double
)
PARTITIONED BY (
    account_id string,
    year int,
    month int
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://<audit-bucket-name>/audit/'
TBLPROPERTIES (
    'classification' = 'json',
    'projection.enabled' = 'true',
    'projection.account_id.type' = 'injected',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2035',
    'projection.month.type' = 'integer',
    'projection.month.range' = '1,12',
    'projection.month.digits' = '2',
    'storage.location.template' = 's3://<audit-bucket-name>/audit/account_id=${account_id}/year=${year}/month=${month}/'
);

-- Example queries to verify partition projection:
-- Note: Because account_id is 'injected', you must always specify a value for account_id in the WHERE clause.
--
-- SELECT * FROM tf2_finops_lakehouse_database.cur_data
-- WHERE account_id = '123456789012' AND year = 2026 AND month = 6
-- LIMIT 10;
--
-- SELECT * FROM tf2_finops_lakehouse_database.containment_audit
-- WHERE account_id = '123456789012' AND year = 2026 AND month = 6
-- LIMIT 10;
