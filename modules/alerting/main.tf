# Alerting Module Resources
# This module creates separate business and engineering alert routes.

resource "aws_sns_topic" "finance" {
  name              = "${var.project_name}-${var.environment}-finance-alerts"
  kms_master_key_id = var.sns_kms_key_arn
  tags              = var.tags
}

resource "aws_sns_topic" "engineering" {
  name              = "${var.project_name}-${var.environment}-engineering-alerts"
  kms_master_key_id = var.sns_kms_key_arn
  tags              = var.tags
}

resource "aws_sns_topic_subscription" "finance" {
  for_each  = toset(var.finance_email_subscriptions)
  topic_arn = aws_sns_topic.finance.arn
  protocol  = "email"
  endpoint  = each.value
}

resource "aws_sns_topic_subscription" "engineering" {
  for_each  = toset(var.engineering_email_subscriptions)
  topic_arn = aws_sns_topic.engineering.arn
  protocol  = "email"
  endpoint  = each.value
}
