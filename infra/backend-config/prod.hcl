# Backend configuration for production environment
# Usage: terraform init -backend-config=backend-config/prod.hcl

bucket         = "code-navigator-terraform-state-prod"
key            = "prod/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "code-navigator-terraform-locks"
encrypt        = true