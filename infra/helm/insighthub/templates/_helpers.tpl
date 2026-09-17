{{- define "insighthub.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "insighthub.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else if contains (include "insighthub.name" .) .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "insighthub.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "insighthub.labels" -}}
app.kubernetes.io/name: {{ include "insighthub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
insighthub.dev/environment: {{ .Values.config.environment | quote }}
{{- end }}

{{- define "insighthub.selectorLabels" -}}
app.kubernetes.io/name: {{ include "insighthub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "insighthub.image" -}}
{{- if .digest -}}
{{ printf "%s@%s" .repository .digest }}
{{- else -}}
{{ printf "%s:%s" .repository .tag }}
{{- end -}}
{{- end }}
