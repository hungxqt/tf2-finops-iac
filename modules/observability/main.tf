data "aws_region" "current" {}

# CloudWatch Metric Alarms

resource "aws_cloudwatch_metric_alarm" "step_functions_failed" {
  alarm_name          = "${var.project_name}-${var.environment}-sfn-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Triggered when Step Functions execution fails"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "step_functions_timed_out" {
  alarm_name          = "${var.project_name}-${var.environment}-sfn-timed-out"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsTimedOut"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Triggered when Step Functions execution times out"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "stale_workflow" {
  alarm_name          = "${var.project_name}-${var.environment}-sfn-stale"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionTime"
  namespace           = "AWS/States"
  period              = 3600
  statistic           = "Maximum"
  threshold           = 93600 # 26 hours in seconds
  alarm_description   = "Triggered when Step Functions execution duration exceeds 26 hours"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each            = toset(var.lambda_function_names)
  alarm_name          = "${var.project_name}-${var.environment}-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Triggered when Lambda function ${each.key} has execution errors"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    FunctionName = each.key
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "drift_detected" {
  alarm_name          = "${var.project_name}-${var.environment}-drift-detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DriftDetected"
  namespace           = "TF2FinOps/CI"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Triggered when infrastructure drift is detected by the CI pipeline"
  alarm_actions       = [var.engineering_topic_arn]
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

# Log Metric Filters for structured Lambda status logs
resource "aws_cloudwatch_log_metric_filter" "lambda_errors" {
  for_each       = toset(var.lambda_function_names)
  name           = "${var.project_name}-${var.environment}-${each.key}-error-filter"
  pattern        = "?ERROR ?Exception ?Failed ?fail ?error"
  log_group_name = "/aws/lambda/${each.key}"

  metric_transformation {
    name      = "${each.key}-structured-errors"
    namespace = "TF2FinOps/LambdaStructuredErrors"
    value     = "1"
  }
}

# CloudWatch Dashboard for FinOps CDO operations
resource "aws_cloudwatch_dashboard" "finops_dashboard" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", var.state_machine_arn],
            [".", "ExecutionsFailed", ".", "."],
            [".", "ExecutionsTimedOut", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Step Functions Execution Status"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            for fn in var.lambda_function_names : [
              "AWS/Lambda", "Errors", "FunctionName", fn
            ]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Lambda Functions Errors"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "stale_telemetry" {
  alarm_name          = "${var.project_name}-${var.environment}-stale-telemetry"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsStarted"
  namespace           = "AWS/States"
  period              = 86400 # 24 hours
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Triggered when no new Step Functions execution starts within 24 hours (stale telemetry signal)"
  alarm_actions       = [var.engineering_topic_arn]
  treat_missing_data  = "breaching"

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "queue_depth" {
  count               = var.detection_queue_name != "" ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-sqs-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 1000
  alarm_description   = "Triggered when SQS primary queue depth exceeds 1000 messages"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    QueueName = var.detection_queue_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  count               = var.detection_dlq_name != "" ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-sqs-dlq-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Triggered when there are messages in the SQS DLQ"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    QueueName = var.detection_dlq_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each            = toset(var.lambda_function_names)
  alarm_name          = "${var.project_name}-${var.environment}-${each.key}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Triggered when Lambda function ${each.key} is throttled"
  alarm_actions       = [var.engineering_topic_arn]

  dimensions = {
    FunctionName = each.key
  }

  tags = var.tags
}


