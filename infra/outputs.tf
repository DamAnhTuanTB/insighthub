output "namespace" {
  description = "Namespace created for the local InsightHub environment."
  value       = module.kubernetes_namespace.namespace
}

output "service_account_name" {
  description = "Tokenless least-privilege service account used by app pods."
  value       = module.kubernetes_namespace.service_account_name
}

output "deployment_profile" {
  description = "Evidence label; this configuration does not verify AWS."
  value       = "local-kubernetes"
}

output "aws_verified" {
  description = "Always false for this local-only Terraform root."
  value       = false
}
