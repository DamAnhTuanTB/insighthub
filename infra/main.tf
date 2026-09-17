locals {
  required_labels = {
    "app.kubernetes.io/name"       = var.project
    "app.kubernetes.io/managed-by" = "terraform"
    "insighthub.dev/environment"   = var.environment
    "insighthub.dev/owner"         = var.owner
    "insighthub.dev/cost-center"   = var.cost_center
  }
}

module "kubernetes_namespace" {
  source = "./modules/kubernetes-namespace"

  namespace            = var.namespace
  service_account_name = var.service_account_name
  labels               = local.required_labels
}
