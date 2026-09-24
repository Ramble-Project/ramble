resource "google_cloudbuild_trigger" "terraform_apply" {
  location    = var.region
  name        = "ramble-terraform-apply"
  description = "Automatically apply Cloud Build Triggers Terraform configuration when pushed to develop branch"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/Ramble-USC1/repositories/${var.github_owner}-${var.github_repo}"
    push {
      branch = "^develop$"
    }
  }

  included_files = [
    "share/ramble/cloud-build/terraform/triggers/**",
    "share/ramble/cloud-build/ramble-terraform-apply.yaml"
  ]

  filename = "share/ramble/cloud-build/ramble-terraform-apply.yaml"
}
