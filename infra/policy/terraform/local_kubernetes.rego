package main

import rego.v1

required_labels := {
  "app.kubernetes.io/name",
  "app.kubernetes.io/managed-by",
  "insighthub.dev/environment",
  "insighthub.dev/owner",
  "insighthub.dev/cost-center",
}

is_managed_kubernetes(change) if {
  change.mode == "managed"
  startswith(change.type, "kubernetes_")
  change.change.after != null
}

deny contains msg if {
  change := input.resource_changes[_]
  is_managed_kubernetes(change)
  metadata := change.change.after.metadata[0]
  label := required_labels[_]
  not metadata.labels[label]
  msg := sprintf("%s must include label %s", [change.address, label])
}

deny contains msg if {
  change := input.resource_changes[_]
  change.type == "kubernetes_namespace_v1"
  change.change.after.metadata[0].name == "default"
  msg := sprintf("%s must not manage the default namespace", [change.address])
}

deny contains msg if {
  change := input.resource_changes[_]
  change.type == "kubernetes_service_account_v1"
  object.get(change.change.after, "automount_service_account_token", true) != false
  msg := sprintf("%s must disable automatic API token mounting", [change.address])
}
