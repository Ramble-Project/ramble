resource "google_cloudbuild_trigger" "image_builders" {
  for_each = local.image_map

  location    = var.region
  name        = "ramble-image-builder-${each.value.base}${replace(each.value.base_ver, ".", "-")}-py${replace(each.value.python, ".", "-")}-spack${replace(each.value.spack, ".", "-")}"
  description = "Build Ramble cloud build image for ${each.value.base} ${each.value.base_ver} with Python ${each.value.python} and Spack ${each.value.spack}"

  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/Ramble-USC1/repositories/${var.github_owner}-${var.github_repo}"
    push {
      branch = "^develop$"
    }
  }

  included_files = concat(
    local.dependency_and_config_files,
    [
      "share/ramble/cloud-build/ramble-image-builder.yaml",
      "share/ramble/cloud-build/Dockerfile-${local.pm_map[each.value.base]}"
    ]
  )

  filename = "share/ramble/cloud-build/ramble-image-builder.yaml"

  substitutions = {
    _PYTHON_VER  = each.value.python
    _SPACK_REF   = each.value.spack
    _PKG_MANAGER = local.pm_map[each.value.base]
    _BASE_IMG    = each.value.base
    _BASE_VER    = each.value.base_ver
  }
}
