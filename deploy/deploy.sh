#!/usr/bin/env bash
# Build the Athena image inside minikube's Docker daemon and (re)install the Helm release
# (web app + Qdrant). Safe to re-run: uses `helm upgrade --install` and rebuilds the image
# each time. Batch ingestion is a separate, opt-in step — see the comment at the bottom.
set -euo pipefail

APP_NAME="athena"
IMAGE_TAG="0.1.0"
NAMESPACE="athena"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHART_DIR="$SCRIPT_DIR/helm/athena"

echo "==> Checking minikube status"
minikube status >/dev/null 2>&1 || minikube start

echo "==> Pointing this shell's Docker CLI at minikube's internal daemon"
eval "$(minikube docker-env)"

echo "==> Building image ${APP_NAME}:${IMAGE_TAG} (context: ${REPO_DIR})"
docker build -t "${APP_NAME}:${IMAGE_TAG}" "${REPO_DIR}"

echo "==> Installing/upgrading Helm release '${APP_NAME}' in namespace '${NAMESPACE}'"
helm upgrade --install "${APP_NAME}" "${CHART_DIR}" \
  --namespace "${NAMESPACE}" --create-namespace \
  --set image.repository="${APP_NAME}" \
  --set image.tag="${IMAGE_TAG}" \
  --wait --timeout 5m

# The image tag is fixed (not versioned per build), so the Deployment's pod template never
# changes and Kubernetes has no reason to roll the pod — force it, otherwise a rebuilt image
# with the same tag silently keeps running in the old container.
echo "==> Forcing rollout so the freshly built image is actually picked up"
kubectl rollout restart deployment/"${APP_NAME}" -n "${NAMESPACE}"
kubectl rollout status deployment/"${APP_NAME}" -n "${NAMESPACE}" --timeout=5m

echo "==> Pods:"
kubectl get pods -n "${NAMESPACE}"

echo "==> Service URL:"
minikube service "${APP_NAME}" -n "${NAMESPACE}" --url

cat <<'EOF'

==> To batch-ingest data:
  1. Copy files onto the shared PVC via the running web pod:
       POD=$(kubectl get pod -n athena -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}')
       kubectl cp ./my_docs athena/"$POD":/app/data/raw/my_docs
  2. Run the ingest Job (creates a fresh, timestamped Job each time):
       helm upgrade --install athena ./deploy/helm/athena -n athena \
         --reuse-values \
         --set batchJob.enabled=true \
         --set batchJob.path=/app/data/raw/my_docs \
         --set batchJob.domain=tech
       kubectl logs -n athena -l app.kubernetes.io/component=ingest-job --tail=-1 -f
EOF
