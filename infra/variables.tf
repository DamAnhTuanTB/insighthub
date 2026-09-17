variable "project" {
  description = "Stable project label."
  type        = string
  default     = "insighthub"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.project))
    error_message = "project must be a lowercase Kubernetes-compatible name."
  }
}

variable "environment" {
  description = "Local environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging"], var.environment)
    error_message = "Local profile supports only dev or staging."
  }
}

variable "owner" {
  description = "Non-secret owner label used for local resource inventory."
  type        = string
  default     = "student"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9_.-]{1,62}$", var.owner))
    error_message = "owner must be a lowercase label-safe value."
  }
}

variable "cost_center" {
  description = "Local resource-accounting label."
  type        = string
  default     = "learning"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9_.-]{1,62}$", var.cost_center))
    error_message = "cost_center must be a lowercase label-safe value."
  }
}

variable "namespace" {
  description = "Namespace dedicated to this InsightHub environment."
  type        = string
  default     = "insighthub-dev"

  validation {
    condition     = can(regex("^insighthub-[a-z0-9-]+$", var.namespace)) && var.namespace != "default"
    error_message = "namespace must start with insighthub- and cannot be default."
  }
}

variable "service_account_name" {
  description = "Least-privilege service account used by application pods."
  type        = string
  default     = "insighthub"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,62}$", var.service_account_name))
    error_message = "service_account_name must be Kubernetes-compatible."
  }
}

variable "kubeconfig_path" {
  description = "Path to kubeconfig. Keep kubeconfig outside the repository."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Explicit local Kubernetes context. Null uses kubeconfig current-context."
  type        = string
  default     = null
  nullable    = true
}
