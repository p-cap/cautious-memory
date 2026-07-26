#!/usr/bin/env bash
# Destroy only Signal Studio resources; never delete the GCP project.
# Terraform owns the private imports bucket with force_destroy enabled, so this
# cleanup also removes its temporary uploaded sources and preview artifacts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/infra/gcp"
TFVARS="$TF_DIR/terraform.tfvars"
PURGE_IMAGES=false

if [[ "${1:-}" == "--purge-images" ]]; then
  PURGE_IMAGES=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--purge-images]" >&2
  exit 1
fi

for command in gcloud terraform; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

if [[ ! -f "$TFVARS" ]]; then
  echo "Missing $TFVARS; refusing to guess a cleanup target." >&2
  exit 1
fi

project_id="$(sed -nE 's/^project_id[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p' "$TFVARS" | head -n1)"
region="$(sed -nE 's/^region[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p' "$TFVARS" | head -n1)"
[[ -n "$project_id" && -n "$region" ]] || { echo "Invalid terraform.tfvars." >&2; exit 1; }

echo "This permanently deletes only these Signal Studio resources in '$project_id':"
echo "  - Cloud Run service and its IAP access bindings"
echo "  - Artifact Registry repository (after its images are removed)"
echo "  - Private imported-project workspace bucket and all temporary source/preview objects"
echo "  - Signal Studio Cloud Run and Cloud Build service accounts"
echo "  - IAM bindings created for those service accounts"
echo "It never deletes the Google Cloud project, your existing website, shared APIs, or unrelated resources."
if [[ "$PURGE_IMAGES" == true ]]; then
  echo "It will also delete every image in $region-docker.pkg.dev/$project_id/signal-studio."
fi
read -r -p "Type DELETE $project_id to continue: " confirmation
[[ "$confirmation" == "DELETE $project_id" ]] || { echo "Cleanup cancelled."; exit 0; }

# Terraform and gcloud both use ADC for this guarded destructive operation.
# Fail before changing project configuration or deleting any resources.
gcloud auth application-default print-access-token >/dev/null
gcloud config set project "$project_id" >/dev/null

if [[ "$PURGE_IMAGES" == true ]]; then
  registry="$region-docker.pkg.dev/$project_id/signal-studio"
  while IFS= read -r image; do
    [[ -n "$image" ]] && gcloud artifacts docker images delete "$image" --delete-tags --quiet
  done < <(gcloud artifacts docker images list "$registry" --include-tags --format='value(URI)' 2>/dev/null | sort -u)
fi

pushd "$TF_DIR" >/dev/null
terraform init -upgrade
terraform plan -destroy
terraform destroy -auto-approve
popd >/dev/null

echo "Signal Studio resources, including its private workspace bucket, were deleted."
