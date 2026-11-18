{{- define "athena.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "athena.fullname" -}}
{{- .Release.Name -}}
{{- end -}}

{{- define "athena.labels" -}}
app.kubernetes.io/name: {{ include "athena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "athena.envFromSecret" -}}
- name: QDRANT_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "athena.fullname" . }}
      key: QDRANT_API_KEY
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "athena.fullname" . }}
      key: OPENAI_API_KEY
- name: ANTHROPIC_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "athena.fullname" . }}
      key: ANTHROPIC_API_KEY
- name: LMSTUDIO_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "athena.fullname" . }}
      key: LMSTUDIO_API_KEY
- name: VLLM_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "athena.fullname" . }}
      key: VLLM_API_KEY
{{- end -}}
