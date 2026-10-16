locals {
  # This map holds the full list of available images.
  # A trigger should always reference these images instead of hard-coding new ones.
  image_map = {
    "debian12-5-py3-12-1-spack-v0-23-1" = { python = "3.12.1", spack = "v0.23.1", base = "debian", base_ver = "12.5" },
    "debian12-5-py3-8-0-spack-v0-23-1"  = { python = "3.8.0", spack = "v0.23.1", base = "debian", base_ver = "12.5" },
    "debian12-5-py3-13-5-spack-v1-2-2"  = { python = "3.13.5", spack = "v1.2.2", base = "debian", base_ver = "12.5" },
    "debian12-5-py3-7-17-spack-v1-2-2"  = { python = "3.7.17", spack = "v1.2.2", base = "debian", base_ver = "12.5" },
    "rocky8-py3-12-1-spack-v0-23-1"     = { python = "3.12.1", spack = "v0.23.1", base = "rockylinux", base_ver = "8" },
    "rocky8-py3-7-0-spack-v0-23-1"      = { python = "3.7.0", spack = "v0.23.1", base = "rockylinux", base_ver = "8" },
    "rocky8-py3-13-5-spack-v1-2-2"      = { python = "3.13.5", spack = "v1.2.2", base = "rockylinux", base_ver = "8" },
    "rocky8-py3-7-17-spack-v1-2-2"      = { python = "3.7.17", spack = "v1.2.2", base = "rockylinux", base_ver = "8" },
    "rocky9-py3-12-1-spack-v0-23-1"     = { python = "3.12.1", spack = "v0.23.1", base = "rockylinux", base_ver = "9" },
    "rocky9-py3-8-0-spack-v0-23-1"      = { python = "3.8.0", spack = "v0.23.1", base = "rockylinux", base_ver = "9" },
    "rocky9-py3-13-5-spack-v1-2-2"      = { python = "3.13.5", spack = "v1.2.2", base = "rockylinux", base_ver = "9" },
    "rocky9-py3-7-17-spack-v1-2-2"      = { python = "3.7.17", spack = "v1.2.2", base = "rockylinux", base_ver = "9" },
  }

  codecov_image_key = "debian12-5-py3-12-1-spack-v0-23-1"

  pm_map = {
    "debian"     = "apt"
    "rockylinux" = "yum"
  }

  docs_files = [
    "lib/ramble/docs/**"
  ]

  core_source_files = [
    "bin/**",
    "lib/ramble/**",
    "var/ramble/repos/**",
    "conftest.py"
  ]

  dependency_and_config_files = [
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-pinned.txt",
    "pyproject.toml",
    "pyproject_objects.toml"
  ]
}
