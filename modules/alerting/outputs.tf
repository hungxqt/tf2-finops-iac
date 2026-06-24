output "finance_topic_arn" {
  description = "The ARN of the Finance SNS Topic"
  value       = aws_sns_topic.finance.arn
}

output "engineering_topic_arn" {
  description = "The ARN of the Engineering SNS Topic"
  value       = aws_sns_topic.engineering.arn
}
