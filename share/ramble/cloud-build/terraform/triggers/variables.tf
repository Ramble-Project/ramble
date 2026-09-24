variable "project_id" {
  type        = string
  description = "The GCP Project ID to host the Cloud Build triggers"
}

variable "region" {
  type        = string
  description = "The GCP Region to deploy the triggers into"
  default     = "us-central1"
}

variable "github_owner" {
  type        = string
  description = "The GitHub organization or user hosting the repository"
  default     = "Ramble-Project"
}

variable "github_repo" {
  type        = string
  description = "The GitHub repository name"
  default     = "ramble"
}
