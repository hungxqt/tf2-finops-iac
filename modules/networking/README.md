# Networking Module

Provisions the VPC and private subnet topology for secure Lambda execution with VPC endpoints for AWS services.

## Usage Example

```hcl
module "networking" {
  source                     = "../../modules/networking"
  project_name               = "tf2-finops"
  environment                = "sandbox"
  aws_region                 = "ap-southeast-1"
  vpc_cidr_block             = "10.0.0.0/16"
  public_subnet_cidr_blocks  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidr_blocks = ["10.0.11.0/24", "10.0.12.0/24"]
  availability_zones         = ["ap-southeast-1a", "ap-southeast-1b"]
  single_nat_gateway         = true
}
```
