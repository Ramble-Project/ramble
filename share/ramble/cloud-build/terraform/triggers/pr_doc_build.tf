resource "google_cloudbuild_trigger" "pr_doc_build_tests" {
  location    = var.region
  name        = "PR-Doc-Build-Tests"
  description = "A presubmit check for building Ramble documentation"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/Ramble-USC1/repositories/${var.github_owner}-${var.github_repo}"
    pull_request {
      branch          = "(?:main|develop)"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
    }
  }

  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  filename = "share/ramble/cloud-build/ramble-pr-docs.yaml"
}
