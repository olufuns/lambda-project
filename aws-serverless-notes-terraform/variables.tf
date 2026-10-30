variable "aws_region" {
  description = "AWS region in which to create resources"
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Resource name prefix; use lowercase letters, numbers and hyphens"
  type        = string
  default     = "serverless-notes-api"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,35}$", var.project_name))
    error_message = "project_name must be 3-36 characters, start with a lowercase letter, and contain lowercase letters, numbers or hyphens."
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days"
  type        = number
  default     = 7
}
