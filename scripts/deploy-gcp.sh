#!/usr/bin/env bash
# Build and deploy Signal Studio to the project configured in infra/gcp/terraform.tfvars.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/infra/gcp"
TFVARS="$TF_DIR/terraform.tfvars"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_command gcloud
require_command terraform
require_command git

if [[ ! -f "$TFVARS" ]]; then
  echo "Missing $TFVARS. Copy terraform.tfvars.example and set the deployment values." >&2
  exit 1
fi

project_id="$(sed -nE 's/^project_id[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p' "$TFVARS" | head -n1)"
region="$(sed -nE 's/^region[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p' "$TFVARS" | head -n1)"

if [[ -z "$project_id" || -z "$region" ]]; then
  echo "terraform.tfvars must set quoted project_id and region values." >&2
  exit 1
fi

echo "This will deploy Signal Studio to project '$project_id' in '$region'."
read -r -p "Type DEPLOY to continue: " confirmation
[[ "$confirmation" == "DEPLOY" ]] || { echo "Deployment cancelled."; exit 0; }

gcloud auth application-default print-access-token >/dev/null
gcloud config set project "$project_id" >/dev/null

pushd "$TF_DIR" >/dev/null
terraform init -upgrade
# Bootstrap APIs, service accounts, IAM, and Artifact Registry before Cloud Build.
terraform apply -auto-approve \
  -target=google_project_service.required \
  -target=google_service_account.runtime \
  -target=google_service_account.build \
  -target=google_artifact_registry_repository.images \
  -target=google_storage_bucket.imports \
  -target=google_project_iam_member.runtime_vertex_ai_user \
  -target=google_storage_bucket_iam_member.runtime_import_access \
  -target=google_project_iam_member.build_artifact_writer \
  -target=google_project_iam_member.build_log_writer \
  -target=google_project_iam_member.build_source_reader \
  -target=google_project_service_identity.iap
popd >/dev/null

tag="$(git -C "$ROOT_DIR" rev-parse --short HEAD)-$(date -u +%Y%m%d%H%M%S)"
image="$region-docker.pkg.dev/$project_id/signal-studio/signal-studio:$tag"

gcloud builds submit "$ROOT_DIR" \
  --config "$ROOT_DIR/cloudbuild.yaml" \
  --project "$project_id" \
  --substitutions="_TAG=$tag"

pushd "$TF_DIR" >/dev/null
terraform apply -auto-approve -var "image=$image"
echo
echo "Deployment complete: $(terraform output -raw service_url)"
popd >/dev/null
