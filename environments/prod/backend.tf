terraform {
  backend "s3" {
    bucket       = "tf2-finops-state-bucket"
    key          = "prod/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    use_lockfile = true
  }
}
