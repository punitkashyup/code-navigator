# Backend configuration for dev environment
# Usage: terraform init -backend-config=backend-config/dev.hcl

bucket                = "code-navigator-terraform-state-punit-1751957892"
key                   = "dev/terraform.tfstate"
region                = "us-east-1"
dynamodb_table        = "code-navigator-terraform-locks"
encrypt               = true