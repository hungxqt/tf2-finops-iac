output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "List of IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "lambda_security_group_id" {
  description = "The ID of the security group for Lambda workers"
  value       = aws_security_group.lambda.id
}

output "vpc_endpoint_security_group_id" {
  description = "The ID of the security group for VPC endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = var.vpc_cidr_block
}



