# Google Cloud deployment

This deployment runs the built Svelte UI and FastAPI API in one Cloud Run
service. That keeps all browser requests same-origin and allows direct Cloud
Run IAP to protect the complete product.

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` and Terraform installed and authenticated
- A Google Group for builder users
- Permission to enable Vertex AI and grant the Cloud Run runtime service account
  the Vertex AI User role

### Required deployer roles

The identity running `scripts/deploy-gcp.sh` needs permission to create the
dedicated service accounts and assign the project IAM bindings defined in
Terraform. Ask a project administrator to grant either temporary **Project
Owner** access for the bootstrap, or this least-privilege set on
`p-cap-476219`:

- Service Account Admin (`roles/iam.serviceAccountAdmin`)
- Project IAM Admin (`roles/resourcemanager.projectIamAdmin`)
- Service Usage Admin (`roles/serviceusage.serviceUsageAdmin`)
- Artifact Registry Administrator (`roles/artifactregistry.admin`)
- Storage Admin (`roles/storage.admin`)
- Cloud Build Editor (`roles/cloudbuild.builds.editor`)
- Cloud Run Admin (`roles/run.admin`)
- IAP Admin (`roles/iap.admin`)
- Service Account User (`roles/iam.serviceAccountUser`)

The administrator can reduce this to custom roles after the initial bootstrap.

## Bootstrap infrastructure

```sh
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars
# Fill in terraform.tfvars. Do not add credentials or API keys here.
terraform init -upgrade
terraform apply
```

The first apply enables the required APIs, creates Artifact Registry and the
private imported-workspace bucket, and creates separate runtime and Cloud Build
service accounts. It grants the runtime account Vertex AI User and object access
to only that private bucket, and grants the build account the minimum permissions
to publish the container image. No model API key, Azure credential, or Secret
Manager value is required. It does not create the Cloud Run service until an
image is supplied.

## Build, deploy, and enable IAP

The guarded script is the recommended way to deploy. It bootstraps Terraform,
builds the image through Cloud Build, deploys the Cloud Run revision, and asks
for an explicit confirmation before changing resources:

```sh
./scripts/deploy-gcp.sh
```

To remove the Terraform-managed Signal Studio service, IAM bindings, service
accounts, Artifact Registry repository, and private imported-workspace bucket
later, use:

```sh
./scripts/cleanup-gcp.sh
```

If the repository has images, Terraform may refuse to delete it. Use
`./scripts/cleanup-gcp.sh --purge-images` only when those images can be
permanently deleted. The cleanup script never deletes the Google Cloud project,
shared APIs, your existing website, or unrelated resources.

## Manual deployment

```sh
PROJECT_ID=YOUR_GCP_PROJECT_ID
REGION=us-central1
TAG=$(git rev-parse --short HEAD)
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/signal-studio/signal-studio:$TAG"

gcloud builds submit ../.. --config ../../cloudbuild.yaml --project "$PROJECT_ID" --substitutions="_TAG=$TAG"
terraform apply -var "image=$IMAGE"
```

Cloud Build builds and publishes the image. The second apply creates the Cloud
Run revision, configures direct Gemini via Vertex AI, enables direct IAP, and
grants the configured Google Group access. The runtime service account obtains
credentials automatically through ADC. Create a Cloud Build trigger using the
same `cloudbuild.yaml` after the first successful release.

Afterwards, open the `service_url` Terraform output. Members of the group
will be prompted to sign in by IAP before the builder or API is reachable.

### Imported-project storage

Cloud Run uses `/tmp` only as an instance-local working cache. After a successful
import, disposable preview, or local apply, the service stores the source and
static preview in a dedicated private bucket named
`signal-studio-imports-<project-number>`. Browsers never access this bucket;
the IAP-protected service hydrates files and serves the preview itself. The
bucket has uniform bucket-level access, public-access prevention, and a lifecycle
rule that deletes imported workspaces after `import_retention_days` (seven days
by default). It excludes the uploaded ZIP, `node_modules`, and build caches.

Changing `import_retention_days` in `terraform.tfvars` changes the automatic
retention period. `cleanup-gcp.sh` deletes the dedicated workspace bucket and
its temporary contents, but never the Google Cloud project or unrelated buckets.

The service is configured with 2 GiB of memory because importing a SvelteKit
archive runs its dependency installation and production build inside Cloud Run.

## Future secrets

If a later integration needs a non-Google credential, create a Secret Manager
secret and inject it into Cloud Run as an environment-variable secret. Do not
put secret values in `terraform.tfvars`, Cloud Build substitutions, or Git.
