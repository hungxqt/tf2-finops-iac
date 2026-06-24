# Uncomment after initial run of bootstrap
# terraform {
#   backend "s3" {
#     bucket         = "tf2-finops-state-bucket"
#     key            = "bootstrap/terraform.tfstate"
#     region         = "ap-southeast-1"
#     encrypt        = true
#     kms_key_id     = "arn:aws:kms:ap-southeast-1:123456789012:key/some-key-id"
#     use_lockfile   = true
#   }
# }
