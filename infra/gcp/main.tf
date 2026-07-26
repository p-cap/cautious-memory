terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Direct Cloud Run IAP is beta-only in the Google provider 6.x series.
provider "google-beta" {
  project = var.project_id
  region  = var.region
}

locals {
  service_name = "signal-studio"
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "iap.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.required_apis
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "current" {}

resource "google_service_account" "runtime" {
  account_id   = "signal-studio-runtime"
  display_name = "Signal Studio Cloud Run runtime"
}

resource "google_service_account" "build" {
  account_id   = "signal-studio-build"
  display_name = "Signal Studio Cloud Build runtime"
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "signal-studio"
  description   = "Signal Studio Cloud Run images"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "imports" {
  name                        = "signal-studio-imports-${data.google_project.current.number}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition { age = var.import_retention_days }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "runtime_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "runtime_import_access" {
  bucket = google_storage_bucket.imports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "build_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.build.email}"
}

resource "google_project_iam_member" "build_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.build.email}"
}

resource "google_project_iam_member" "build_source_reader" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.build.email}"
}

resource "google_project_service_identity" "iap" {
  provider = google-beta
  project  = var.project_id
  service  = "iap.googleapis.com"

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "app" {
  provider = google-beta
  count    = var.image == "" ? 0 : 1
  name     = local.service_name
  location = var.region

  # Direct IAP protects the run.app endpoint without a separate load balancer.
  iap_enabled = true
  # Allows the guarded cleanup script to delete this service, not the project.
  deletion_protection = false

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "300s"
    max_instance_request_concurrency = 10

    scaling {
      # Imported workspaces are persisted in the private bucket, so requests
      # can safely land on different instances.
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.image

      ports { container_port = 8080 }

      resources {
        limits = {
          cpu = "1"
          # Imported SvelteKit projects run npm install and npm run build in
          # this process. 1 GiB was exceeded during an import; 2 GiB leaves
          # room for Node, the Python service, and the extracted workspace.
          memory = "2Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.vertex_ai_location
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "True"
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "IMPORT_BUCKET"
        value = google_storage_bucket.imports.name
      }
    }
  }

  depends_on = [
    google_project_iam_member.runtime_vertex_ai_user,
    google_storage_bucket_iam_member.runtime_import_access,
  ]
}

# IAP, not the public internet, invokes the service.
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  count    = length(google_cloud_run_v2_service.app)
  location = google_cloud_run_v2_service.app[0].location
  name     = google_cloud_run_v2_service.app[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap.email}"
}

# Access is group-based so membership changes do not require an application deploy.
resource "google_iap_web_cloud_run_service_iam_member" "builder_users" {
  count                  = length(google_cloud_run_v2_service.app)
  project                = var.project_id
  location               = google_cloud_run_v2_service.app[0].location
  cloud_run_service_name = google_cloud_run_v2_service.app[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "group:${var.iap_access_group}"
}
