#!/bin/bash

# Simple script to create S3 bucket and DynamoDB table for Terraform backend

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Creating Terraform Backend Resources${NC}"
echo "===================================="

# Generate unique bucket name
BUCKET_NAME="code-navigator-terraform-state-$(whoami)-$(date +%s)"

echo -e "${YELLOW}Creating S3 bucket: ${BUCKET_NAME}${NC}"

# Create S3 bucket
aws s3 mb "s3://${BUCKET_NAME}"

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --server-side-encryption-configuration '{
        "Rules": [
            {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }
        ]
    }'

# Block public access
aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo -e "${YELLOW}Creating DynamoDB table for state locking${NC}"

# Create DynamoDB table
aws dynamodb create-table \
    --table-name code-navigator-terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

echo -e "${GREEN}✓ Backend resources created successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Update backend-config/dev.hcl with bucket name: ${BUCKET_NAME}"
echo "2. Run: terraform init -backend-config=backend-config/dev.hcl"
echo "3. Run: terraform workspace new dev"
echo "4. Continue with your infrastructure deployment"
echo ""
echo -e "${YELLOW}S3 Bucket: ${BUCKET_NAME}${NC}"
echo -e "${YELLOW}DynamoDB Table: code-navigator-terraform-locks${NC}"

# Update the backend config file automatically
echo -e "${YELLOW}Updating backend-config/dev.hcl...${NC}"
cat > backend-config/dev.hcl << EOF
# Backend configuration for dev environment
# Usage: terraform init -backend-config=backend-config/dev.hcl

bucket         = "${BUCKET_NAME}"
key            = "dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "code-navigator-terraform-locks"
encrypt        = true
EOF

echo -e "${GREEN}✓ Updated backend-config/dev.hcl${NC}"