output "artifact_repository" {
  value = google_artifact_registry_repository.images.name
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "import_workspace_bucket" {
  description = "Private bucket holding temporary imported site workspaces."
  value       = google_storage_bucket.imports.name
}

output "service_url" {
  value = try(google_cloud_run_v2_service.app[0].uri, null)
}
