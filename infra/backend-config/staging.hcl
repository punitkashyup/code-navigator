# Backend configuration for staging environment
# Usage: terraform init -backend-config=backend-config/staging.hcl

bucket         = "code-navigator-terraform-state-staging"
key            = "staging/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "code-navigator-terraform-locks"
encrypt        = true