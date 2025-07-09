variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for OpenSearch"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
}

variable "instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "t3.small.search"
}

variable "instance_count" {
  description = "Number of OpenSearch instances"
  type        = number
  default     = 2
  
  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 10
    error_message = "Instance count must be between 1 and 10."
  }
}

variable "volume_size" {
  description = "EBS volume size for OpenSearch (GB)"
  type        = number
  default     = 20
  
  validation {
    condition     = var.volume_size >= 10 && var.volume_size <= 1000
    error_message = "Volume size must be between 10 and 1000 GB."
  }
}

variable "master_user" {
  description = "OpenSearch master username"
  type        = string
  default     = "admin"
}

variable "master_password" {
  description = "OpenSearch master password"
  type        = string
  sensitive   = true
  
  validation {
    condition     = length(var.master_password) >= 8
    error_message = "Master password must be at least 8 characters long."
  }
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}