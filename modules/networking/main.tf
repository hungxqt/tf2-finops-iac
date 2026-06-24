# Networking Module Resources
# This module implements the private network foundation.

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-vpc"
    }
  )
}

# Internet Gateway
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-igw"
    }
  )
}

# Public Subnets (NAT Gateway hosting)
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr_blocks[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-public-subnet-${count.index + 1}"
    }
  )
}

# Private Subnets (Lambda worker hosting)
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr_blocks[count.index]
  availability_zone = var.availability_zones[count.index]
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-private-subnet-${count.index + 1}"
    }
  )
}

# Elastic IPs for NAT
resource "aws_eip" "nat" {
  count  = var.single_nat_gateway ? 1 : 2
  domain = "vpc"
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-nat-eip-${count.index + 1}"
    }
  )
}

# NAT Gateways
resource "aws_nat_gateway" "nat" {
  count         = var.single_nat_gateway ? 1 : 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-nat-gw-${count.index + 1}"
    }
  )
  depends_on = [aws_internet_gateway.gw]
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-public-rt"
    }
  )
}

# Private Route Table(s)
resource "aws_route_table" "private" {
  count  = var.single_nat_gateway ? 1 : 2
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat[count.index].id
  }
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-private-rt-${count.index + 1}"
    }
  )
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = var.single_nat_gateway ? aws_route_table.private[0].id : aws_route_table.private[count.index].id
}

# Lambda Security Group
resource "aws_security_group" "lambda" {
  name        = "${var.project_name}-${var.environment}-lambda-sg"
  description = "Security group for Lambda workers"
  vpc_id      = aws_vpc.main.id
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-sg"
    }
  )
}

# Egress only for Lambda SG
resource "aws_security_group_rule" "lambda_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.lambda.id
  description       = "Allow all outbound traffic from Lambda"
}

# VPC Endpoint Security Group
resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project_name}-${var.environment}-endpoints-sg"
  description = "Security group for VPC interface endpoints"
  vpc_id      = aws_vpc.main.id
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-endpoints-sg"
    }
  )
}

# Ingress from VPC and Lambda
resource "aws_security_group_rule" "endpoints_ingress_vpc_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_block]
  security_group_id = aws_security_group.vpc_endpoints.id
  description       = "Allow HTTPS from within the VPC"
}

resource "aws_security_group_rule" "endpoints_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.vpc_endpoints.id
  description       = "Allow all outbound traffic from endpoints"
}

# S3 Gateway Endpoint
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat(
    [aws_route_table.public.id],
    aws_route_table.private[*].id
  )
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-s3-endpoint"
    }
  )
}

# DynamoDB Gateway Endpoint
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat(
    [aws_route_table.public.id],
    aws_route_table.private[*].id
  )
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-dynamodb-endpoint"
    }
  )
}

# Interface Endpoints
locals {
  interface_services = ["kms", "secretsmanager", "athena", "logs", "xray", "sts"]
}

resource "aws_vpc_endpoint" "interfaces" {
  for_each            = toset(local.interface_services)
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  subnet_ids          = aws_subnet.private[*].id
  private_dns_enabled = true
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-${each.key}-endpoint"
    }
  )
}
