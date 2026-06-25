# Uncomment after initial run of bootstrap
terraform {
  backend "s3" {
    bucket       = "tf2-finops-state-bucket"
    key          = "bootstrap/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    kms_key_id   = "arn:aws:kms:ap-southeast-1:093490087544:key/f0382479-e89e-41af-8041-89d10f275bf4"
    use_lockfile = true
  }
}
