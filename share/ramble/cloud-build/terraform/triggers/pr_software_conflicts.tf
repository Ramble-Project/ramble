locals {
  pr_software_conflicts_img = local.image_map["rocky8-py3-12-1-spack-v0-22-1"]
}

resource "google_cloudbuild_trigger" "pr_software_conflicts" {
  location    = var.region
  name        = "PR-Software-Conflicts-${local.pr_software_conflicts_img.base}${local.pr_software_conflicts_img.base_ver}-${replace(local.pr_software_conflicts_img.spack, ".", "-")}spack-${replace(local.pr_software_conflicts_img.python, ".", "-")}python"
  description = "Check for conflicts in application definitions on Ramble pull requests"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/Ramble-USC1/repositories/${var.github_owner}-${var.github_repo}"
    pull_request {
      branch          = "(?:main|develop)"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
    }
  }

  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  filename = "share/ramble/cloud-build/ramble-pr-software-conflicts.yaml"

  included_files = [
    "var/ramble/repos/**",
    "lib/ramble/ramble/**",
    "examples/**",
    "share/ramble/cloud-build/**",
    "share/ramble/qa/check_configs.py"
  ]

  substitutions = {
    _BASE_IMG   = local.pr_software_conflicts_img.base
    _BASE_VER   = local.pr_software_conflicts_img.base_ver
    _PYTHON_VER = local.pr_software_conflicts_img.python
    _SPACK_REF  = local.pr_software_conflicts_img.spack
  }
}
