terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Backend configuration will be provided via backend config file
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = terraform.workspace
      Project     = var.project_name
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  common_tags = {
    Environment = terraform.workspace
    Project     = var.project_name
    ManagedBy   = "terraform"
  }
  
  name_prefix = "${var.project_name}-${terraform.workspace}"
}

# VPC and Networking
module "vpc" {
  source = "./modules/vpc"
  
  name_prefix     = local.name_prefix
  cidr_block      = var.vpc_cidr
  azs             = var.availability_zones
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets
  
  tags = local.common_tags
}

# Security Groups
module "security" {
  source = "./modules/security"
  
  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  
  tags = local.common_tags
}

# EC2 for MCP Server
module "ec2" {
  source = "./modules/ec2"
  
  name_prefix           = local.name_prefix
  vpc_id               = module.vpc.vpc_id
  public_subnet_ids    = module.vpc.public_subnet_ids
  private_subnet_ids   = module.vpc.private_subnet_ids
  security_group_ids   = [module.security.ec2_security_group_id]
  
  instance_type        = var.ec2_instance_type
  key_name            = var.ec2_key_name
  
  # MCP Server configuration
  mcp_server_image     = var.mcp_server_image
  mcp_server_port      = var.mcp_server_port
  opensearch_endpoint  = module.opensearch.endpoint
  
  # Docker build automation
  auto_build_docker = var.auto_build_docker
  
  # Environment variables for MCP server
  opensearch_master_user     = var.opensearch_master_user
  opensearch_master_password = var.opensearch_master_password
  github_token               = var.github_token
  openai_api_key             = var.openai_api_key
  mcp_api_key                = var.mcp_api_key
  aws_region                 = data.aws_region.current.name
  aws_account_id             = data.aws_caller_identity.current.account_id
  
  tags = local.common_tags
}

# Application Load Balancer
module "alb" {
  source = "./modules/alb"
  
  name_prefix        = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  security_group_ids = [module.security.alb_security_group_id]
  
  # Target groups
  mcp_server_target_group_arn = module.ec2.target_group_arn
  
  # SSL/TLS
  domain_name        = var.domain_name
  certificate_arn    = var.certificate_arn
  
  tags = local.common_tags
}

# Lambda Function for Webhook
module "lambda" {
  source = "./modules/lambda"
  
  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids
  security_group_ids = [module.security.lambda_security_group_id]
  
  # Environment variables
  opensearch_endpoint = module.opensearch.endpoint
  opensearch_user     = var.opensearch_master_user
  opensearch_password = var.opensearch_master_password
  github_webhook_secret = var.github_webhook_secret
  github_token         = var.github_token
  openai_api_key      = var.openai_api_key
  mcp_api_key         = var.mcp_api_key
  
  # Docker build automation
  auto_build_docker = var.auto_build_docker
  enable_lambda_creation = var.enable_lambda_creation
  
  tags = local.common_tags
}

# OpenSearch
module "opensearch" {
  source = "./modules/opensearch"
  
  name_prefix       = local.name_prefix
  vpc_id           = module.vpc.vpc_id
  subnet_ids       = module.vpc.private_subnet_ids
  security_group_ids = [module.security.opensearch_security_group_id]
  
  instance_type    = var.opensearch_instance_type
  instance_count   = var.opensearch_instance_count
  volume_size      = var.opensearch_volume_size
  
  master_user      = var.opensearch_master_user
  master_password  = var.opensearch_master_password
  
  tags = local.common_tags
}

# GuardDuty
module "guardduty" {
  source = "./modules/guardduty"
  
  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  
  tags = local.common_tags
}