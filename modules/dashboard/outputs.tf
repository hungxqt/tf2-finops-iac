output "athena_named_query_ids" {
  description = "List of IDs for the Athena named queries created"
  value = [
    aws_athena_named_query.spend_by_service.id,
    aws_athena_named_query.spend_by_account.id,
    aws_athena_named_query.anomaly_spend_trends.id
  ]
}

output "quicksight_enabled" {
  description = "Boolean flag indicating whether QuickSight resources were enabled"
  value       = var.enable_quicksight
}
