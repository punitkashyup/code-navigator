# Manual Terraform Setup Instructions

Since the automated script is having issues with duplicate resources, here's a simple manual approach:

## Step 1: Create the Backend Resources

```bash
# Create a unique S3 bucket for Terraform state
BUCKET_NAME="code-navigator-terraform-state-$(whoami)-$(date +%s)"
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

# Create DynamoDB table for locking
aws dynamodb create-table \
    --table-name code-navigator-terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

echo "Backend resources created:"
echo "S3 Bucket: ${BUCKET_NAME}"
echo "DynamoDB Table: code-navigator-terraform-locks"
```

## Step 2: Update Backend Configuration

Edit `backend-config/dev.hcl` and replace the bucket name:

```hcl
bucket         = "your-actual-bucket-name-from-step1"
key            = "dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "code-navigator-terraform-locks"
encrypt        = true
```

## Step 3: Initialize Terraform

```bash
# Initialize with the backend
terraform init -backend-config=backend-config/dev.hcl

# Create and select dev workspace
terraform workspace new dev

# Verify you're in the right workspace
terraform workspace show
```

## Step 4: Plan and Apply

```bash
# Review what will be created
terraform plan -var-file=environments/dev.tfvars

# Apply the infrastructure
terraform apply -var-file=environments/dev.tfvars
```

## If You Get Errors

If you encounter any issues:

1. **Clean up and start over:**
   ```bash
   rm -rf .terraform* terraform.tfstate*
   ```

2. **Check your AWS credentials:**
   ```bash
   aws sts get-caller-identity
   ```

3. **Verify the bucket exists:**
   ```bash
   aws s3 ls | grep code-navigator
   ```

4. **Check DynamoDB table:**
   ```bash
   aws dynamodb describe-table --table-name code-navigator-terraform-locks
   ```