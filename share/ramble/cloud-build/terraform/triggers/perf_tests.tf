locals {
  perf_test_img = local.image_map["rocky8-py3-13-5-spack-v1-0-0"]
}

resource "google_cloudbuild_worker_pool" "perf_test_pool" {
  name         = "n2d-perf-test-pool"
  location     = var.region
  display_name = "Private N2D worker pool for Ramble performance tests"

  worker_config {
    machine_type = "n2d-standard-16"
    disk_size_gb = 100
  }
}

resource "google_cloudbuild_trigger" "perf_test_pr" {
  location    = var.region
  name        = "PerfTest-PR-${local.perf_test_img.base}${local.perf_test_img.base_ver}-${replace(local.perf_test_img.spack, ".", "-")}spack-${replace(local.perf_test_img.python, ".", "-")}python"
  description = "Ramble perf tests for PR builds"

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
      "share/ramble/**"
    ]
  )

  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  filename = "share/ramble/cloud-build/ramble-perf-tests.yaml"

  substitutions = {
    _SPACK_REF    = local.perf_test_img.spack
    _PYTHON_VER   = local.perf_test_img.python
    _BASE_IMG     = local.perf_test_img.base
    _BASE_VER     = local.perf_test_img.base_ver
    _DATASET_ID   = "ramble_metrics"
    _PROJECT_ID   = var.project_id
    _TABLE_ID     = "perf_test_durations"
    _UPLOAD_TO_BQ = "false"
    _WORKER_POOL  = google_cloudbuild_worker_pool.perf_test_pool.id
  }
}

resource "google_cloudbuild_trigger" "perf_test_push" {
  location    = var.region
  name        = "PerfTest-Push-${local.perf_test_img.base}${local.perf_test_img.base_ver}-${replace(local.perf_test_img.spack, ".", "-")}spack-${replace(local.perf_test_img.python, ".", "-")}python"
  description = "Continuous monitoring of Ramble performance for develop push"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/Ramble-USC1/repositories/${var.github_owner}-${var.github_repo}"
    push {
      branch = "^develop$"
    }
  }

  filename = "share/ramble/cloud-build/ramble-perf-tests.yaml"

  substitutions = {
    _SPACK_REF    = local.perf_test_img.spack
    _PYTHON_VER   = local.perf_test_img.python
    _BASE_IMG     = local.perf_test_img.base
    _BASE_VER     = local.perf_test_img.base_ver
    _DATASET_ID   = "ramble_metrics"
    _PROJECT_ID   = var.project_id
    _TABLE_ID     = "perf_test_durations"
    _UPLOAD_TO_BQ = "true"
    _WORKER_POOL  = google_cloudbuild_worker_pool.perf_test_pool.id
  }
}
