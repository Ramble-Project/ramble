resource "google_cloudbuild_worker_pool" "unit_test_pool" {
  name         = "n2d-unit-test-pool"
  location     = "southamerica-west1"
  display_name = "Private N2D worker pool for Ramble unit tests"

  worker_config {
    machine_type = "n2d-standard-8"
    disk_size_gb = 100
  }
}

resource "google_cloudbuild_trigger" "pr_unit_tests" {
  for_each = local.image_map

  location    = google_cloudbuild_worker_pool.unit_test_pool.location
  name        = "PR-Unit-Tests-${each.value.base}${replace(each.value.base_ver, ".", "-")}-${replace(each.value.spack, ".", "-")}spack-${replace(each.value.python, ".", "-")}python"
  description = "Run unit tests and linting on Ramble pull requests"

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
      "share/ramble/cloud-build/**"
    ]
  )

  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  filename = "share/ramble/cloud-build/ramble-pr-unit-tests.yaml"

  substitutions = {
    _BASE_IMG    = each.value.base
    _BASE_VER    = each.value.base_ver
    _PYTHON_VER  = each.value.python
    _SPACK_REF   = each.value.spack
    _WORKER_POOL = google_cloudbuild_worker_pool.unit_test_pool.id
  }
}
