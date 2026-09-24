locals {
  pr_doc_img = local.image_map["rocky8-py3-13-5-spack-v1-0-0"]
}

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

  substitutions = {
    _BASE_IMG   = local.pr_doc_img.base
    _BASE_VER   = local.pr_doc_img.base_ver
    _PYTHON_VER = local.pr_doc_img.python
    _SPACK_REF  = local.pr_doc_img.spack
  }
}
