locals {
  pr_style_img = local.image_map["rocky8-py3-12-1-spack-v0-22-1"]
}

resource "google_cloudbuild_trigger" "pr_style" {
  location    = var.region
  name        = "PR-Style-${local.pr_style_img.base}${local.pr_style_img.base_ver}-${replace(local.pr_style_img.spack, ".", "-")}spack-${replace(local.pr_style_img.python, ".", "-")}python"
  description = "Run linting on Ramble pull requests"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/Ramble-USC1/repositories/${var.github_owner}-${var.github_repo}"
    pull_request {
      branch          = "(?:main|develop)"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
    }
  }

  ignored_files = local.docs_files

  included_files = concat(
    local.core_source_files,
    local.dependency_and_config_files,
    [
      "share/ramble/cloud-build/**"
    ]
  )

  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  filename = "share/ramble/cloud-build/ramble-pr-style.yaml"

  substitutions = {
    _BASE_IMG   = local.pr_style_img.base
    _BASE_VER   = local.pr_style_img.base_ver
    _PYTHON_VER = local.pr_style_img.python
    _SPACK_REF  = local.pr_style_img.spack
  }
}
