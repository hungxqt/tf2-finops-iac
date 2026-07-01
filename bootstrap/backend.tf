# Uncomment after initial run of bootstrap
terraform {
  backend "s3" {
    bucket       = "tf2-finops-state-bucket"
    key          = "bootstrap/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    use_lockfile = true
  }
}
