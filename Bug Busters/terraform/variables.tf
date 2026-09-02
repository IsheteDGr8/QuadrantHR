variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint"
  type        = string
}

variable "azure_openai_api_key" {
  description = "Azure OpenAI API key"
  type        = string
  sensitive   = true
}

variable "azure_openai_deployment" {
  description = "Azure OpenAI deployment name"
  type        = string
}

# Placeholder — has a default so `terraform plan/apply` doesn't break in CI
# before the team wires a real address into the bugbusters-common variable
# group. Override via TF_VAR_alert_email once there's a real on-call
# address/distribution list to page.
variable "alert_email" {
  description = "Email address that receives SRE alert notifications"
  type        = string
  default     = "devops-placeholder@bugbusters.example"
}