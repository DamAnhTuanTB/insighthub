variable "namespace" {
  description = "Dedicated namespace for one InsightHub environment."
  type        = string
}

variable "service_account_name" {
  description = "Application service account name."
  type        = string
}

variable "labels" {
  description = "Required inventory and ownership labels."
  type        = map(string)
}
