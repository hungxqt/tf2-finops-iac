output "export_arn" {
  description = "ARN of the AWS Data Exports CUR 2.0 export"
  value       = aws_bcmdataexports_export.cur.export[0].export_arn
}

output "export_name" {
  description = "Name of the AWS Data Exports CUR 2.0 export"
  value       = aws_bcmdataexports_export.cur.export[0].name
}

output "s3_prefix" {
  description = "S3 prefix where the export writes CUR files"
  value       = "${trim(var.destination_prefix, "/")}/${var.export_name}"
}
