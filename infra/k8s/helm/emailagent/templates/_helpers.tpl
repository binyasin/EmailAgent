{{- define "emailagent.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "emailagent.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "emailagent.labels" -}}
app.kubernetes.io/name: {{ include "emailagent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "emailagent.controlPlane.selectorLabels" -}}
app.kubernetes.io/name: {{ include "emailagent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: control-plane
{{- end -}}

{{- define "emailagent.dashboard.selectorLabels" -}}
app.kubernetes.io/name: {{ include "emailagent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: dashboard
{{- end -}}

{{- define "emailagent.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- printf "%s-sa" (include "emailagent.fullname" .) -}}
{{- else -}}
default
{{- end -}}
{{- end -}}
