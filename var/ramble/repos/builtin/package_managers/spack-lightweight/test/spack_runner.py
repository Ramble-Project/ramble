# Copyright 2022-2025 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.config
from ramble.pkg_man.builtin.spack_lightweight import (
    InvalidExternalEnvironment,
    SpackRunner,
)
from ramble.util.command_runner import RunnerError


def test_env_create(tmpdir, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner()
        sr.create_env(env_path)
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_activate(tmpdir, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner()
        sr.create_env(env_path)
        sr.activate()
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_deactivate(tmpdir, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner()
        sr.create_env(env_path)
        sr.activate()
        sr.deactivate()
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_add(tmpdir, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner()
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")
        sr.deactivate()
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_concretize(tmpdir, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner()
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")
        sr.concretize()
        sr.deactivate()

        assert os.path.exists(os.path.join(env_path, "spack.yaml"))
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_concretize_skips_already_concretized_envs(
    tmpdir, capsys, request
):
    import time

    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner()
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")
        sr.add_spec("intel-oneapi-mpi")

        # Generate an initial env file
        stage_env_path = sr.create_stage_env()
        sr.migrate_stage_env(stage_env_path, env_path)

        time.sleep(0.5)

        # Create a spack.lock file in the env
        with open(
            os.path.join(env_path, "spack.lock"), "w+", encoding="utf-8"
        ) as f:
            f.write("")

        # Mock regenerating an env file, after the lock was created.
        sr.migrate_stage_env(stage_env_path, env_path)

        sr.concretize()

        output = capsys.readouterr()
        assert "is already concretized. Skipping concretize..." in output.out

        sr.deactivate()

        assert os.path.exists(os.path.join(env_path, "spack.yaml"))
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_install(tmpdir, capsys, request):
    try:
        env_path = str(tmpdir.join(request.node.name))
        # Dry run so we don't actually install zlib
        sr = SpackRunner(dry_run=True)
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")
        stage_env_path = sr.create_stage_env()
        sr.migrate_stage_env(stage_env_path, env_path)
        sr.concretize()
        sr.install()

        captured = capsys.readouterr()
        assert "spack install" in captured.out

        sr.deactivate()

        env_file = os.path.join(env_path, "spack.yaml")

        assert os.path.exists(env_file)

        with open(env_file, encoding="utf-8") as f:
            assert "zlib" in f.read()

    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_configs_apply(tmpdir, capsys, request):
    try:
        env_path = str(tmpdir.join(request.node.name))
        # Dry run so we don't actually install zlib
        sr = SpackRunner(dry_run=True)
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")
        sr.add_config("config:debug:true")
        stage_env_path = sr.create_stage_env()
        sr.apply_configs(stage_path=stage_env_path)

        captured = capsys.readouterr()
        assert (
            f"with args: ['-D', '{stage_env_path}', 'config', 'add', 'config:debug:true']"
            in captured.out
        )

        sr.migrate_stage_env(stage_env_path, env_path)

        sr.deactivate()

        env_file = os.path.join(env_path, "spack.yaml")

        assert os.path.exists(env_file)

        with open(env_file, encoding="utf-8") as f:
            data = f.read()
            assert "zlib" in data
            assert "debug: true" in data

    except RunnerError as e:
        pytest.skip("%s" % e)


@pytest.mark.parametrize("link_type", ["symlink", "hardlink", "copy"])
def test_env_view_link_types(tmpdir, request, link_type, mutable_config):
    with ramble.config.override(
        "config:spack:", {"env_view": {"link_type": f"{link_type}"}}
    ):
        try:
            env_path = str(tmpdir.join(request.node.name))
            # Dry run so we don't actually install zlib
            sr = SpackRunner(dry_run=True)
            sr.create_env(env_path)
            sr.activate()
            sr.add_spec("zlib")
            stage_env_path = sr.create_stage_env()
            sr.apply_configs(stage_path=stage_env_path)
            sr.migrate_stage_env(stage_env_path, env_path)

            sr.deactivate()

            env_file = os.path.join(env_path, "spack.yaml")

            assert os.path.exists(env_file)

            with open(env_file, encoding="utf-8") as f:
                data = f.read()
                assert f"link_type: {link_type}" in data

        except RunnerError as e:
            pytest.skip("%s" % e)


def test_default_concretize_flags(tmpdir, capsys, request, config):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner(dry_run=True)
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")

        sr.concretize()
        captured = capsys.readouterr()
        assert "spack concretize" in captured.out
        assert "with args: ['--fresh']" in captured.out
    except RunnerError as e:
        pytest.skip("%s" % e)


@pytest.mark.parametrize(
    "attr,value,expected_str",
    [
        ("flags", "-f --fresh", "'-f', '--fresh'"),
        ("prefix", "time", "would run time"),
    ],
)
def test_config_concretize_attribute(
    tmpdir, capsys, attr, value, expected_str, request
):
    try:
        env_path = tmpdir.join(request.node.name)
        with ramble.config.override(
            "config:spack", {"concretize": {attr: value}}
        ):
            sr = SpackRunner(dry_run=True)
            sr.create_env(env_path)
            sr.activate()
            sr.add_spec("zlib")

            sr.concretize()
            captured = capsys.readouterr()

            assert expected_str in captured.out
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_default_install_flags(tmpdir, capsys, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner(dry_run=True)
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")

        sr.concretize()
        sr.install()
        captured = capsys.readouterr()

        install_flags = ramble.config.config.get("config:spack:install:flags")
        expected_str = "with args: ["
        str_args = [f"'{flag}'" for flag in install_flags.split()]
        expected_str += ",".join(str_args) + "]"

        assert "spack install" in captured.out
    except RunnerError as e:
        pytest.skip("%s" % e)


@pytest.mark.parametrize(
    "attr,value,expected_str",
    [
        ("flags", "--fresh --keep-prefix", "'--fresh', '--keep-prefix'"),
        ("prefix", "time", "would run time"),
    ],
)
def test_config_install_attribute(
    tmpdir, capsys, attr, value, expected_str, request
):
    try:
        env_path = tmpdir.join(request.node.name)
        with ramble.config.override(
            "config:spack", {"install": {attr: value}}
        ):
            sr = SpackRunner(dry_run=True)
            sr.create_env(env_path)
            sr.activate()
            sr.add_spec("zlib")
            sr.concretize()

            sr.install()
            captured = capsys.readouterr()

            assert expected_str in captured.out
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_env_include(tmpdir, capsys, request):
    try:
        env_path = tmpdir.join(request.node.name)
        sr = SpackRunner(dry_run=True)
        sr.create_env(env_path)
        sr.activate()
        sr.add_spec("zlib")
        good_include_path = "/path/to/include/config.yaml"
        bad_include_path = "/path/to/include/junk.yaml"
        sr.add_include_file(good_include_path)
        sr.add_include_file(bad_include_path)
        stage_env_path = sr.create_stage_env()
        sr.migrate_stage_env(stage_env_path, env_path)

        sr.concretize()

        with open(os.path.join(env_path, "spack.yaml"), encoding="utf-8") as f:
            data = f.read()
            assert good_include_path in data
            assert bad_include_path not in data
    except RunnerError as e:
        pytest.skip("%s" % e)


def test_new_compiler_installs(tmpdir, capsys, request):

    import os

    with tmpdir.as_cwd():
        # compilers.yaml is written to support older spack versions.
        # The compiler information was changed to exist in the packages.yaml file around v1.0.0
        tmpdir_bin = os.path.join(os.getcwd(), "bin")
        env_path = os.path.join(os.getcwd(), "test_env")
        os.mkdir(env_path)
        os.mkdir(tmpdir_bin)
        compilers_config = f"""
compilers::
- compiler:
    spec: gcc@12.1.0
    paths:
      cc: {tmpdir_bin}/gcc
      cxx: {tmpdir_bin}/g++
      f77: {tmpdir_bin}/gfortran
      fc: {tmpdir_bin}/gfortran
    flags: {{}}
    operating_system: 'ramble'
    target: 'x86_64'
    modules: []
    environment: {{}}
    extra_rpaths: []
"""

        packages_config = f"""
packages:
  gcc:
    externals:
    - spec: gcc@12.1.0 languages=c,fortran
      prefix: {os.getcwd()}
      extra_attributes:
        compilers:
          c: {tmpdir_bin}/gcc
          cxx: {tmpdir_bin}/g++
          fortran: {tmpdir_bin}/gfortran
    buildable: false
"""

        packages_path = os.path.join(tmpdir, "packages.yaml")
        compilers_path = os.path.join(tmpdir, "compilers.yaml")
        # Write spack_configs
        with open(packages_path, "w+", encoding="utf-8") as f:
            f.write(packages_config)

        with open(compilers_path, "w+", encoding="utf-8") as f:
            f.write(compilers_config)

        config_path = tmpdir
        with ramble.config.override(
            "config:spack", {"global": {"flags": f"-C {config_path}"}}
        ):
            try:
                pkg_spec = "gcc@12.1.0 +binutils"
                compiler_spec = "gcc@12.1.0"
                sr = SpackRunner(dry_run=True)
                sr.create_env(env_path)
                sr.activate()
                sr.add_include_file(packages_path)
                sr.add_include_file(compilers_path)
                stage_env_path = sr.create_stage_env()
                sr.migrate_stage_env(stage_env_path, env_path)
                sr.install_compiler("gcc@12.1.0 +binutils", "gcc@12.1.0")
                captured = capsys.readouterr()

                assert (
                    f"{compiler_spec} is already an available compiler"
                    in captured.out
                )

                assert f"{pkg_spec}" not in captured.out
            except RunnerError as e:
                pytest.skip("%s" % e)


def test_external_env_copies(tmpdir, request):
    src_spack_yaml = """
spack:
  specs: [ 'zlib' ]
"""

    src_spack_lock = """
{
  "_meta": {
    "file-type": "spack-lockfile",
    "lockfile-version": 4,
    "specfile-version": 3
  },
  "roots": [
    {
      "hash": "hdw7vo7aap7mqx34ipo3nkzwshctnbnv",
      "spec": "zlib"
    }
  ],
  "concrete_specs": {
    "hdw7vo7aap7mqx34ipo3nkzwshctnbnv": {
      "name": "zlib",
      "version": "1.2.13",
      "arch": {
        "platform": "test_platform",
        "platform_os": "test_os",
        "target": {
          "name": "test_target",
          "vendor": "test_vendor",
          "features": [
            "adx",
          ],
          "generation": 0,
          "parents": [
            "broadwell"
          ]
        }
      },
      "compiler": {
        "name": "gcc",
        "version": "12.2.0"
      },
      "namespace": "builtin",
      "parameters": {
        "build_system": "makefile",
        "optimize": true,
        "pic": true,
        "shared": true,
        "cflags": [],
        "cppflags": [],
        "cxxflags": [],
        "fflags": [],
        "ldflags": [],
        "ldlibs": []
      },
      "package_hash": "y6ahhnjjjsfh5dx2y7sci7fhthq5aolyl5dgwif57qqbtjxwdwbq====",
      "hash": "hdw7vo7aap7mqx34ipo3nkzwshctnbnv"
    }
  }
}
"""

    with tmpdir.as_cwd():
        with open(
            os.path.join(os.getcwd(), "spack.yaml"), "w+", encoding="utf-8"
        ) as f:
            f.write(src_spack_yaml)

        with open(
            os.path.join(os.getcwd(), "spack.lock"), "w+", encoding="utf-8"
        ) as f:
            f.write(src_spack_lock)

        try:
            sr = SpackRunner(dry_run=True)
            generated_env = os.path.join(os.getcwd(), "dest_env")
            sr.create_env(os.path.join(generated_env))
            sr.activate()
            sr.copy_from_external_env(os.getcwd())

            assert os.path.exists(os.path.join(generated_env, "spack.yaml"))

            with open(
                os.path.join(generated_env, "spack.yaml"), encoding="utf-8"
            ) as f:
                assert "zlib" in f.read()
        except RunnerError as e:
            pytest.skip("%s" % e)


def test_configs_apply_to_external_env(tmpdir, request):
    src_spack_yaml = """
spack:
  specs: [ 'zlib' ]
"""
    with tmpdir.as_cwd():
        with open(
            os.path.join(os.getcwd(), "spack.yaml"), "w+", encoding="utf-8"
        ) as f:
            f.write(src_spack_yaml)

        try:
            sr = SpackRunner(dry_run=True)
            generated_env = os.path.join(os.getcwd(), "dest_env")
            sr.create_env(os.path.join(generated_env))
            sr.activate()
            sr.add_config("config:debug:true")
            stage_env_path = sr.create_stage_env()
            sr.copy_from_external_env(os.getcwd(), stage_path=stage_env_path)
            sr.apply_configs(stage_path=stage_env_path)
            sr.migrate_stage_env(stage_env_path, generated_env)

            assert os.path.exists(os.path.join(generated_env, "spack.yaml"))

            with open(
                os.path.join(generated_env, "spack.yaml"), encoding="utf-8"
            ) as f:
                data = f.read()
                assert "zlib" in data
                assert "config:" in data
                assert "debug: true" in data
        except RunnerError as e:
            pytest.skip("%s" % e)


def test_invalid_external_env_errors(tmpdir, request):
    with tmpdir.as_cwd():
        try:
            sr = SpackRunner(dry_run=True)
            generated_env = os.path.join(os.getcwd(), "dest_env")
            sr.create_env(os.path.join(generated_env))
            sr.activate()
            with pytest.raises(InvalidExternalEnvironment):
                sr.copy_from_external_env(os.getcwd())
        except RunnerError as e:
            pytest.skip("%s" % e)


@pytest.mark.parametrize(
    "attr,value,expected_str",
    [
        ("flags", "--scope site", "'--scope', 'site'"),
    ],
)
def test_config_compiler_find_attribute(
    tmpdir, capsys, attr, value, expected_str, request
):

    import os

    # compilers.yaml is written to support older spack versions.
    # The compiler information was changed to exist in the packages.yaml file around v1.0.0
    compilers_config = """
compilers::
- compiler:
    spec: gcc@12.1.0
    paths:
      cc: /path/to/gcc
      cxx: /path/to/g++
      f77: /path/to/gfortran
      fc: /path/to/gfortran
    flags: {}
    operating_system: 'ramble'
    target: 'x86_64'
    modules: []
    environment: {}
    extra_rpaths: []
"""

    packages_config = """
packages::
  gcc:
    externals:
    - spec: gcc@12.1.0 languages=c,fortran
      prefix: /path/to
      extra_attributes:
        compilers:
          c: /path/to/gcc
          cxx: /path/to/g++
          fortran: /path/to/gfortran
    buildable: false
"""

    with tmpdir.as_cwd():
        env_path = os.path.join(os.getcwd(), "test_env")
        os.mkdir(env_path)
        packages_path = os.path.join(os.getcwd(), "packages.yaml")
        compilers_path = os.path.join(os.getcwd(), "compilers.yaml")
        # Write spack_configs
        with open(packages_path, "w+", encoding="utf-8") as f:
            f.write(packages_config)

        with open(compilers_path, "w+", encoding="utf-8") as f:
            f.write(compilers_config)

        config_path = os.getcwd()
        with ramble.config.override(
            "config:spack", {"global": {"flags": f"-C {config_path}"}}
        ):
            with ramble.config.override(
                "config:spack", {"compiler_find": {attr: value}}
            ):
                try:
                    pkg_spec = "gcc@12.2.0 +binutils"
                    compiler_spec = "gcc@12.2.0"
                    sr = SpackRunner(dry_run=True)
                    sr.create_env(env_path)
                    sr.activate()
                    sr.add_include_file(packages_path)
                    sr.add_include_file(compilers_path)
                    stage_env_path = sr.create_stage_env()
                    sr.migrate_stage_env(stage_env_path, env_path)
                    sr.install_compiler(pkg_spec, compiler_spec)
                    captured = capsys.readouterr()

                    assert expected_str in captured.out
                except RunnerError as e:
                    pytest.skip("%s" % e)


def test_env_create_no_view(tmpdir, request):

    import os

    with tmpdir.as_cwd():
        with ramble.config.override(
            "config:spack", {"env_create": {"flags": "--without-view"}}
        ):
            try:
                sr = SpackRunner()
                sr.create_env(os.getcwd())

                assert not os.path.exists(
                    os.path.join(os.getcwd(), ".spack-env", "view")
                )
            except RunnerError as e:
                pytest.skip("%s" % e)


def test_multiword_args(tmpdir, capsys, request):
    try:
        env_path = tmpdir.join(request.node.name)
        with ramble.config.override(
            "config:spack",
            {"install": {"flags": 'install="-multiword -args"'}},
        ):
            sr = SpackRunner(dry_run=True)
            sr.create_env(env_path)
            sr.activate()
            sr.add_spec("zlib")
            sr.concretize()

            sr.install()
            sr.get_package_path('zlib package_path="-multiword -args"')
            captured = capsys.readouterr()
            print(captured.out)

            assert "install=-multiword -args" in captured.out
            assert "package_path=-multiword -args" in captured.out
    except RunnerError as e:
        pytest.skip("%s" % e)
