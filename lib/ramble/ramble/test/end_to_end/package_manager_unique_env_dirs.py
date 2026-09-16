# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.workspace
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")
config = RambleCommand("config")


def test_env_dirs_do_not_collide(mutable_config, mutable_mock_workspace_path, workspace_name):
    ws = ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    # Add tests to workspace
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "env_name=multiple_env",
        "-V",
        "package_manager=spack",
        "--wf",
        "water_bare",
        global_args=global_args,
    )

    workspace(
        "manage",
        "experiments",
        "pip-test",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "env_name=multiple_env",
        "-V",
        "package_manager=pip",
        "--wf",
        "import",
        global_args=global_args,
    )

    # Add software packages to workspace
    config("add", "software:packages:package:spack_pkg_spec:gromacs", global_args=global_args)
    config("add", "software:packages:package:pip_pkg_spec:semver", global_args=global_args)

    config("add", "software:environments:multiple_env:packages:[package]", global_args=global_args)

    workspace("setup", "--dry-run", global_args=global_args)

    # Check pip and spack directories exist
    spack_dir = __import__("glob").glob(os.path.join(ws.software_dir, "spack*"))[0]
    pip_dir = os.path.join(ws.software_dir, "pip")

    for pm_dir in [spack_dir, pip_dir]:
        assert os.path.isdir(pm_dir)
        env_dir = os.path.join(pm_dir, "multiple_env")
        assert os.path.isdir(env_dir)

        req_file = os.path.join(env_dir, "requirements.txt")
        spack_file = os.path.join(env_dir, "spack.yaml")

        if os.path.isfile(req_file):
            with open(req_file, encoding="utf-8") as f:
                content = f.read()
                assert "gromacs" not in content
                assert "semver" in content
        elif os.path.isfile(spack_file):
            with open(spack_file, encoding="utf-8") as f:
                content = f.read()
                assert "gromacs" in content
                assert "semver" not in content


def test_multiple_spack_versions_env_dirs_do_not_collide(
    tmp_path, mutable_config, mutable_mock_workspace_path, mutable_systems, workspace_name
):
    # Set up mock systems repo
    sys_repo_dir = tmp_path / "sys_repo"
    sys_repo_dir.mkdir()
    (sys_repo_dir / "repo.yaml").write_text("repo:\n  namespace: mock_sys_repo\n")

    sys_dir1 = sys_repo_dir / "systems" / "spack-sys-v102"
    sys_dir1.mkdir(parents=True)
    with open(str(sys_dir1 / "system.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.syskit import *

class SpackSysV102(SystemBase):
    name = "spack-sys-v102"
    default_package_manager("spack")
    requires_utility("spack", tag="v1.0.2", allow_external=False)
    variable("max_nodes", default="10", description="Max nodes")
    variable("max_cores_per_node", default="16", description="Max cores")
""")

    sys_dir2 = sys_repo_dir / "systems" / "spack-sys-v023"
    sys_dir2.mkdir(parents=True)
    with open(str(sys_dir2 / "system.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.syskit import *

class SpackSysV023(SystemBase):
    name = "spack-sys-v023"
    default_package_manager("spack")
    requires_utility("spack", tag="v0.23.0", allow_external=False)
    variable("max_nodes", default="10", description="Max nodes")
    variable("max_cores_per_node", default="16", description="Max cores")
""")

    sys_repo = ramble.repository.Repo(
        str(sys_repo_dir), object_type=ramble.repository.ObjectTypes.systems
    )
    mutable_systems.put_first(sys_repo)

    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "hostname",
        "-e",
        "exp_v102",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "env_name=shared_env",
        "-V",
        "system=spack-sys-v102",
        "--wf",
        "serial",
        global_args=global_args,
    )

    workspace(
        "manage",
        "experiments",
        "hostname",
        "-e",
        "exp_v023",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "env_name=shared_env",
        "-V",
        "system=spack-sys-v023",
        "--wf",
        "serial",
        global_args=global_args,
    )

    config("add", "software:packages:package:spack_pkg_spec:zlib", global_args=global_args)
    config("add", "software:environments:shared_env:packages:[package]", global_args=global_args)

    workspace("setup", "--dry-run", global_args=global_args)

    # Check both distinct spack software directories exist
    spack_dirs = __import__("glob").glob(os.path.join(ws.software_dir, "spack-spack*"))
    assert len(spack_dirs) == 2

    # One directory corresponds to v1.0.2 and the other to v0.23.0
    dir_names = [os.path.basename(d) for d in spack_dirs]
    assert any("1.0.2" in name or "v1.0.2" in name for name in dir_names)
    assert any("0.23.0" in name or "v0.23.0" in name for name in dir_names)

    for spack_dir in spack_dirs:
        env_dir = os.path.join(spack_dir, "shared_env")
        assert os.path.isdir(env_dir)
        spack_file = os.path.join(env_dir, "spack.yaml")
        assert os.path.isfile(spack_file)
        with open(spack_file, encoding="utf-8") as f:
            content = f.read()
            assert "zlib" in content

    exp1_script = os.path.join(
        ws.root, "experiments", "hostname", "serial", "exp_v102", "execute_experiment"
    )
    exp2_script = os.path.join(
        ws.root, "experiments", "hostname", "serial", "exp_v023", "execute_experiment"
    )
    assert os.path.isfile(exp1_script)
    assert os.path.isfile(exp2_script)

    with open(exp1_script, encoding="utf-8") as f:
        exp1_content = f.read()
        assert "1.0.2" in exp1_content or "v1.0.2" in exp1_content
        assert "0.23.0" not in exp1_content and "v0.23.0" not in exp1_content

    with open(exp2_script, encoding="utf-8") as f:
        exp2_content = f.read()
        assert "0.23.0" in exp2_content or "v0.23.0" in exp2_content
        assert "1.0.2" not in exp2_content and "v1.0.2" not in exp2_content
