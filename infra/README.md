# CodeNavigator Infrastructure

This Terraform configuration creates a complete AWS infrastructure for the CodeNavigator application, including:

- **VPC**: Custom Virtual Private Cloud with public and private subnets
- **EC2**: Instance hosting the MCP server using Docker
- **ALB**: Application Load Balancer with HTTPS support
- **Lambda**: Webhook handler for GitHub integration
- **OpenSearch**: Managed search and analytics service
- **GuardDuty**: Threat detection and security monitoring

## Architecture

The infrastructure is designed with security and scalability in mind:

- Public subnets host the ALB and NAT gateways
- Private subnets host EC2, Lambda, and OpenSearch for security
- GuardDuty provides threat detection across all resources
- All services support HTTP Host header flexibility for proxy compatibility

## Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **Terraform** >= 1.0 installed
3. **Domain name** (optional, for HTTPS setup)
4. **SSL Certificate** in ACM (optional, or will be auto-created)

## Quick Start

### 1. Initialize Backend (First Time Only)

```bash
# Initialize Terraform without backend first
terraform init

# Create the S3 bucket and DynamoDB table for state management
terraform apply -target=aws_s3_bucket.terraform_state -target=aws_dynamodb_table.terraform_locks

# Now configure the backend
terraform init -backend-config=backend-config/dev.hcl
```

### 2. Create Environment Workspace

```bash
# Create and select workspace
terraform workspace new dev
terraform workspace select dev
```

### 3. Plan and Apply

```bash
# Review the plan
terraform plan -var-file=environments/dev.tfvars

# Apply the configuration
terraform apply -var-file=environments/dev.tfvars
```

## Environment Management

This setup uses Terraform workspaces and environment-specific `.tfvars` files:

- **dev**: Development environment with minimal resources
- **staging**: Staging environment with moderate resources
- **prod**: Production environment with high availability

### Switching Environments

```bash
# Switch to staging
terraform workspace select staging
terraform plan -var-file=environments/staging.tfvars
terraform apply -var-file=environments/staging.tfvars

# Switch to production
terraform workspace select prod
terraform plan -var-file=environments/prod.tfvars
terraform apply -var-file=environments/prod.tfvars
```

## Configuration

### Required Variables

Before deploying, update the following in your `.tfvars` file:

```hcl
# Security
opensearch_master_password = "YourSecurePassword123!"
github_webhook_secret      = "your-github-webhook-secret"

# Optional but recommended
ec2_key_name    = "your-ec2-key-pair"
domain_name     = "your-domain.com"
certificate_arn = "arn:aws:acm:region:account:certificate/cert-id"
github_token    = "github_pat_xxxxx"
openai_api_key  = "sk-xxxxx"
```

### Environment Variables

You can also use environment variables for sensitive values:

```bash
export TF_VAR_opensearch_master_password="YourSecurePassword123!"
export TF_VAR_github_webhook_secret="your-webhook-secret"
export TF_VAR_github_token="github_pat_xxxxx"
export TF_VAR_openai_api_key="sk-xxxxx"
```

## Modules

The infrastructure is organized into the following modules:

- **vpc**: Virtual Private Cloud and networking
- **security**: Security groups and IAM policies
- **ec2**: EC2 instance and Auto Scaling
- **alb**: Application Load Balancer and SSL termination
- **lambda**: Webhook Lambda function and API Gateway
- **opensearch**: Managed OpenSearch cluster
- **guardduty**: Threat detection and monitoring

## Deployment Process

### Development

```bash
terraform workspace select dev
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

### Staging

```bash
terraform workspace select staging
terraform plan -var-file=environments/staging.tfvars
terraform apply -var-file=environments/staging.tfvars
```

### Production

```bash
terraform workspace select prod
terraform plan -var-file=environments/prod.tfvars
terraform apply -var-file=environments/prod.tfvars
```

## Outputs

After deployment, Terraform will output important information:

- **ALB DNS Name**: Load balancer endpoint
- **OpenSearch Endpoint**: Search cluster endpoint
- **Webhook URL**: GitHub webhook endpoint
- **MCP Server URL**: MCP service endpoint

## Security Considerations

1. **Passwords**: Change default passwords in `.tfvars` files
2. **SSH Access**: Restrict EC2 SSH access to specific IP ranges
3. **Secrets**: Use AWS Systems Manager Parameter Store for production secrets
4. **VPC**: Resources are deployed in private subnets where possible
5. **GuardDuty**: Enabled for threat detection and monitoring

## SSL/HTTPS Setup

### Option 1: Existing Certificate

If you have an existing ACM certificate:

```hcl
domain_name     = "your-domain.com"
certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012"
```

### Option 2: Auto-Generated Certificate

Set only the domain name, and Terraform will create and validate the certificate:

```hcl
domain_name = "your-domain.com"
certificate_arn = ""
```

### Option 3: HTTP Only

Leave both empty for HTTP-only deployment:

```hcl
domain_name     = ""
certificate_arn = ""
```

## Monitoring and Logging

The infrastructure includes comprehensive monitoring:

- **CloudWatch Logs**: Application and system logs
- **CloudWatch Metrics**: Performance and health metrics
- **CloudWatch Alarms**: Automated alerting
- **GuardDuty**: Security threat detection
- **VPC Flow Logs**: Network traffic monitoring

## Troubleshooting

### Common Issues

1. **Backend State Lock**: If Terraform state is locked, check DynamoDB table
2. **Certificate Validation**: DNS validation may take time for new domains
3. **OpenSearch Access**: Ensure security groups allow proper communication
4. **Lambda Timeout**: Check CloudWatch logs for function errors

### Useful Commands

```bash
# Show current workspace
terraform workspace show

# List all workspaces
terraform workspace list

# Show state
terraform show

# Refresh state
terraform refresh -var-file=environments/dev.tfvars

# Import existing resources
terraform import aws_instance.example i-1234567890abcdef0
```

## Cleanup

To destroy the infrastructure:

```bash
# Destroy specific environment
terraform workspace select dev
terraform destroy -var-file=environments/dev.tfvars

# Note: Some resources like S3 buckets may need to be emptied first
```

## Support

For issues and questions:

1. Check the Terraform documentation
2. Review AWS service documentation
3. Check CloudWatch logs for application issues
4. Verify security group and IAM permissions