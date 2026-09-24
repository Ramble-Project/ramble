data "google_secret_manager_secret_version" "codecov_token" {
  secret  = "ramble-codecov-token"
  version = "latest"
}

locals {
  codecov_image = local.image_map["debian12-5-py3-12-0-spack-v0-21-2"]
}

resource "google_cloudbuild_trigger" "codecov_pr" {
  location    = google_cloudbuild_worker_pool.unit_test_pool.location
  name        = "Codecov-PR-Unit-Tests-${local.codecov_image.base}${replace(local.codecov_image.base_ver, ".", "-")}-py${replace(local.codecov_image.python, ".", "-")}-spack${replace(local.codecov_image.spack, ".", "-")}"
  description = "Run unit tests and linting on Ramble pull requests with Codecov upload"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${google_cloudbuild_worker_pool.unit_test_pool.location}/connections/Ramble-SAW1/repositories/${var.github_owner}-${var.github_repo}"
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
      ".github/codecov.yml",
      "share/ramble/cloud-build/**",
      "share/ramble/qa/**"
    ]
  )

  filename = "share/ramble/cloud-build/ramble-pr-unit-tests.yaml"

  substitutions = {
    _BASE_IMG      = local.codecov_image.base
    _BASE_VER      = local.codecov_image.base_ver
    _PYTHON_VER    = local.codecov_image.python
    _SPACK_REF     = local.codecov_image.spack
    _PUSH_CODECOV  = "true"
    _CODECOV_TOKEN = data.google_secret_manager_secret_version.codecov_token.secret_data
    _WORKER_POOL   = google_cloudbuild_worker_pool.unit_test_pool.id
  }
}

resource "google_cloudbuild_trigger" "codecov_push" {
  location    = google_cloudbuild_worker_pool.unit_test_pool.location
  name        = "Codecov-BasePush-${local.codecov_image.base}${replace(local.codecov_image.base_ver, ".", "-")}-py${replace(local.codecov_image.python, ".", "-")}-spack${replace(local.codecov_image.spack, ".", "-")}"
  description = "Collect coverage information on develop or main pushes"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${google_cloudbuild_worker_pool.unit_test_pool.location}/connections/Ramble-SAW1/repositories/${var.github_owner}-${var.github_repo}"
    push {
      branch = "(?:main|develop)"
    }
  }

  filename = "share/ramble/cloud-build/ramble-pr-unit-tests.yaml"

  substitutions = {
    _BASE_IMG      = local.codecov_image.base
    _BASE_VER      = local.codecov_image.base_ver
    _PYTHON_VER    = local.codecov_image.python
    _SPACK_REF     = local.codecov_image.spack
    _PUSH_CODECOV  = "true"
    _CODECOV_TOKEN = data.google_secret_manager_secret_version.codecov_token.secret_data
    _WORKER_POOL   = google_cloudbuild_worker_pool.unit_test_pool.id
  }
}
