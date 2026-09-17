resource "kubernetes_namespace_v1" "this" {
  metadata {
    name   = var.namespace
    labels = var.labels
  }
}

resource "kubernetes_service_account_v1" "application" {
  automount_service_account_token = false

  metadata {
    name      = var.service_account_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = var.labels
  }
}
