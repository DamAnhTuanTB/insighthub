package main

import rego.v1

workload_kinds := {"Deployment", "StatefulSet"}

is_workload if {
  workload_kinds[input.kind]
}

containers contains container if {
  is_workload
  container := input.spec.template.spec.containers[_]
}

deny contains msg if {
  is_workload
  not input.metadata.labels["app.kubernetes.io/name"]
  msg := sprintf("%s/%s must have app.kubernetes.io/name", [input.kind, input.metadata.name])
}

deny contains msg if {
  is_workload
  object.get(input.spec.template.spec, "automountServiceAccountToken", true) != false
  msg := sprintf("%s/%s must disable service account token automount", [input.kind, input.metadata.name])
}

deny contains msg if {
  is_workload
  pod_security_context := object.get(input.spec.template.spec, "securityContext", {})
  object.get(pod_security_context, "runAsNonRoot", false) != true
  msg := sprintf("%s/%s must run as non-root", [input.kind, input.metadata.name])
}

deny contains msg if {
  container := containers[_]
  not container.resources.requests.cpu
  msg := sprintf("container %s must request CPU", [container.name])
}

deny contains msg if {
  container := containers[_]
  not container.resources.requests.memory
  msg := sprintf("container %s must request memory", [container.name])
}

deny contains msg if {
  container := containers[_]
  not container.resources.limits.cpu
  msg := sprintf("container %s must limit CPU", [container.name])
}

deny contains msg if {
  container := containers[_]
  not container.resources.limits.memory
  msg := sprintf("container %s must limit memory", [container.name])
}

deny contains msg if {
  container := containers[_]
  security_context := object.get(container, "securityContext", {})
  object.get(security_context, "allowPrivilegeEscalation", true) != false
  msg := sprintf("container %s must disable privilege escalation", [container.name])
}

deny contains msg if {
  container := containers[_]
  security_context := object.get(container, "securityContext", {})
  object.get(security_context, "readOnlyRootFilesystem", false) != true
  msg := sprintf("container %s must use a read-only root filesystem", [container.name])
}

deny contains msg if {
  container := containers[_]
  security_context := object.get(container, "securityContext", {})
  capabilities := object.get(security_context, "capabilities", {})
  drops := object.get(capabilities, "drop", [])
  not "ALL" in drops
  msg := sprintf("container %s must drop all Linux capabilities", [container.name])
}

deny contains msg if {
  container := containers[_]
  endswith(container.image, ":latest")
  msg := sprintf("container %s must not use a latest image tag", [container.name])
}

deny contains msg if {
  input.kind == "Service"
  input.spec.type == "LoadBalancer"
  msg := sprintf("Service/%s must not allocate a cloud load balancer in the local profile", [input.metadata.name])
}
