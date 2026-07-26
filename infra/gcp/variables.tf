variable "project_id" {
  description = "Google Cloud project that will own the service."
  type        = string
}

variable "region" {
  description = "Cloud Run and Artifact Registry region."
  type        = string
  default     = "us-central1"
}

variable "image" {
  description = "Artifact Registry image URI. Leave blank for the bootstrap apply."
  type        = string
  default     = ""
}

variable "iap_access_group" {
  description = "Google Group allowed to open Signal Studio through IAP."
  type        = string
}

variable "vertex_ai_location" {
  description = "Vertex AI location used for direct Gemini calls."
  type        = string
  default     = "global"
}

variable "gemini_model" {
  description = "Gemini model used to generate local proposals."
  type        = string
  default     = "gemini-2.5-flash"
}

variable "import_retention_days" {
  description = "Days to retain private imported workspaces and previews in Cloud Storage."
  type        = number
  default     = 7
}
