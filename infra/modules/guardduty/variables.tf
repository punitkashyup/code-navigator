variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "trusted_ip_list" {
  description = "List of trusted IP addresses to whitelist"
  type        = list(string)
  default     = []
}

variable "threat_intel_list" {
  description = "List of known malicious IP addresses"
  type        = list(string)
  default     = []
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for GuardDuty alerts"
  type        = string
  default     = ""
}

variable "member_accounts" {
  description = "Map of member accounts to invite to GuardDuty"
  type = map(object({
    account_id = string
    email      = string
  }))
  default = {}
}

variable "enable_organization_configuration" {
  description = "Enable GuardDuty organization configuration"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}