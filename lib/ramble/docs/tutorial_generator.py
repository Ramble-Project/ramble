# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import json
import os
import re
import shutil
import subprocess
import tempfile
import yaml
try:
    import pty
except ImportError:
    pty = None


def load_all_recipes(docs_src_dir):
    """Load all tutorial recipes and selectable applications from modular or legacy recipe files."""
    recipes = {}
    selectable_applications = {}

    # 1. Load legacy monolithic file if present (for backward compatibility)
    legacy_file = os.path.join(docs_src_dir, "tutorial_recipes.yaml")
    if os.path.exists(legacy_file):
        with open(legacy_file, "r") as f:
            data = yaml.safe_load(f) or {}
            recipes.update(data.get("recipes", {}))
            selectable_applications.update(data.get("selectable_applications", {}))

    # 2. Load selectable applications definition
    selectable_apps_file = os.path.join(
        docs_src_dir, "tutorials", "selectable_applications.yaml"
    )
    if os.path.exists(selectable_apps_file):
        with open(selectable_apps_file, "r") as f:
            data = yaml.safe_load(f) or {}
            selectable_applications.update(data.get("selectable_applications", {}))

    # 3. Discover and load per-tutorial recipe files in docs/tutorials/
    tutorials_dir = os.path.join(docs_src_dir, "tutorials")
    if os.path.isdir(tutorials_dir):
        for fname in sorted(os.listdir(tutorials_dir)):
            if fname.endswith(".yaml") or fname.endswith(".yml"):
                if fname == "selectable_applications.yaml":
                    continue
                file_path = os.path.join(tutorials_dir, fname)
                with open(file_path, "r") as f:
                    file_data = yaml.safe_load(f) or {}
                    if "recipes" in file_data:
                        recipes.update(file_data["recipes"])
                    elif "recipe" in file_data:
                        if isinstance(file_data["recipe"], dict):
                            recipes.update(file_data["recipe"])
                    elif "recipe_id" in file_data:
                        r_id = file_data["recipe_id"]
                        recipes[r_id] = {k: v for k, v in file_data.items() if k != "recipe_id"}

    return recipes, selectable_applications


def _sanitize_output(text, ws_dir, ws_name="hello_world"):
    if not text:
        return text
    ws_base = os.path.basename(ws_dir)
    # Replace absolute ws path
    text = text.replace(ws_dir, f"/path/to/{ws_name}")
    # Replace temporary workspace basename if referenced in output
    text = re.sub(rf"From Workspace: {re.escape(ws_base)}.*", f"From Workspace: {ws_name}", text)
    text = re.sub(rf"Workspace: {re.escape(ws_base)}", f"Workspace: {ws_name}", text)
    # Sanitize variable timestamps in log paths and results filenames
    text = re.sub(r"\.\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}\b", ".<timestamp>", text)
    text = re.sub(
        r"results\.\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}\.txt", "results.<timestamp>.txt", text
    )
    # Sanitize dynamic machine hostname in results snippet
    text = re.sub(r"possible hostname = .*", "possible hostname = my_host", text)
    return text


def _run_cmd_for_snippet(cmd_args, use_pty=False):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    if use_pty and pty is not None:
        master, slave = pty.openpty()
        proc = subprocess.Popen(cmd_args, stdin=slave, stdout=slave, stderr=slave, close_fds=True)
        os.close(slave)
        out = b""
        while True:
            try:
                chunk = os.read(master, 1024)
                if not chunk:
                    break
                out += chunk
            except OSError:
                break
        os.close(master)
        proc.wait()
        res = out.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "")
        return ansi_escape.sub("", res)
    else:
        proc = subprocess.Popen(
            cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        out, _ = proc.communicate()
        return ansi_escape.sub("", out)


def generate_tutorial_snippets(docs_src_dir):
    """Generate command and YAML snippets for tutorials using Ramble workspace manage."""
    import ramble.paths
    from ramble.main import RambleCommand

    ramble_bin = os.path.join(ramble.paths.ramble_root, "bin", "ramble")

    recipes, _ = load_all_recipes(docs_src_dir)
    if not recipes:
        return

    output_dir = os.path.join(docs_src_dir, "_generated", "snippets")
    os.makedirs(output_dir, exist_ok=True)

    for recipe_id, recipe in recipes.items():
        apps = recipe.get("apps", {})
        for app_id, app_info in apps.items():
            ws_dir = tempfile.mkdtemp(prefix=f"ramble_tut_{recipe_id}_{app_id}_")
            try:
                # 0. Output custom named snippets if present
                custom_snippets = app_info.get("snippets", {})
                for snippet_name, snippet_content in custom_snippets.items():
                    snippet_path = os.path.join(
                        output_dir, f"{recipe_id}_{app_id}_{snippet_name}.yaml"
                    )
                    with open(snippet_path, "w") as f:
                        if isinstance(snippet_content, dict):
                            f.write(yaml.dump(snippet_content, sort_keys=False))
                        else:
                            f.write(str(snippet_content).strip() + "\n")

                # Execute each command in sandbox workspace
                for step in app_info.get("commands", []):
                    # Check if step has command_file
                    if step.get("command_file") and step.get("display"):
                        cmd_file_path = os.path.join(
                            output_dir, f"{recipe_id}_{app_id}_{step['command_file']}"
                        )
                        with open(cmd_file_path, "w") as f:
                            f.write(step["display"].strip() + "\n")

                    # Check if step is reading a file rather than running a command
                    if step.get("read_file"):
                        src_path = step["read_file"].replace("{ws}", ws_dir)
                        if os.path.exists(src_path) and step.get("output_file"):
                            with open(src_path, "r") as f:
                                file_content = f.read()
                            ws_name = app_info.get("workspace_name") or (
                                recipe_id if recipe_id != "default" else app_id
                            )
                            sanitized = _sanitize_output(file_content, ws_dir, ws_name)
                            out_file_path = os.path.join(
                                output_dir, f"{recipe_id}_{app_id}_{step['output_file']}"
                            )
                            with open(out_file_path, "w") as f:
                                f.write(sanitized)
                        continue

                    raw_cmd = step.get("cmd")
                    if not raw_cmd:
                        continue
                    cmd = [
                        arg.replace("{ws}", ws_dir) if isinstance(arg, str) else arg
                        for arg in raw_cmd
                    ]
                    cmd_name = cmd[0]
                    sub_args = cmd[1:]

                    use_workspace = step.get("use_workspace", True)
                    use_pty = step.get("use_pty", False)
                    output_file = step.get("output_file")
                    global_args = list(step.get("global_args", []))

                    if output_file or use_pty:
                        # Run via subprocess / pty to accurately capture terminal output
                        full_exec_cmd = [ramble_bin]
                        if use_pty:
                            full_exec_cmd.append("--color=never")
                        full_exec_cmd.extend(global_args)
                        if use_workspace and not (cmd_name == "workspace" and sub_args and sub_args[0] == "create"):
                            full_exec_cmd.extend(["-D", ws_dir])
                        full_exec_cmd.extend(cmd)

                        captured_out = _run_cmd_for_snippet(full_exec_cmd, use_pty=use_pty)
                        if output_file:
                            ws_name = app_info.get("workspace_name") or (
                                recipe_id if recipe_id != "default" else app_id
                            )
                            sanitized = _sanitize_output(captured_out, ws_dir, ws_name)
                            out_file_path = os.path.join(
                                output_dir, f"{recipe_id}_{app_id}_{output_file}"
                            )
                            with open(out_file_path, "w") as f:
                                f.write(sanitized)
                    else:
                        runner = RambleCommand(cmd_name)
                        if cmd_name == "workspace" and sub_args and sub_args[0] == "create":
                            runner(*sub_args)
                        elif not use_workspace:
                            runner(*sub_args, global_args=global_args if global_args else None)
                        else:
                            runner(*sub_args, global_args=["-D", ws_dir] + global_args)

                # 1. Output formatted commands
                display_cmds = [
                    step.get("display", "")
                    for step in app_info.get("commands", [])
                    if step.get("display") and step.get("in_commands_sh", True)
                ]
                if display_cmds:
                    commands_path = os.path.join(
                        output_dir, f"{recipe_id}_{app_id}_commands.sh"
                    )
                    with open(commands_path, "w") as f:
                        f.write("\n".join(display_cmds) + "\n")

                # 2. Output generated ramble.yaml
                ramble_yaml_path = os.path.join(ws_dir, "configs", "ramble.yaml")
                if "final" in custom_snippets or "ramble" in custom_snippets:
                    final_content = custom_snippets.get("final") or custom_snippets.get("ramble")
                    yaml_content = str(final_content).strip() + "\n"
                elif os.path.exists(ramble_yaml_path):
                    with open(ramble_yaml_path, "r") as f:
                        yaml_content = f.read()
                else:
                    yaml_content = None

                if yaml_content:
                    full_yaml_dest = os.path.join(
                        output_dir, f"{recipe_id}_{app_id}_ramble.yaml"
                    )
                    with open(full_yaml_dest, "w") as f:
                        f.write(yaml_content)

                    # 3. Output extracted applications dictionary
                    parsed = yaml.safe_load(yaml_content)
                    if parsed and "ramble" in parsed and "applications" in parsed["ramble"]:
                        apps_dict = {"applications": parsed["ramble"]["applications"]}
                        apps_yaml = yaml.dump(apps_dict, sort_keys=False)
                        apps_yaml_dest = os.path.join(
                            output_dir, f"{recipe_id}_{app_id}_applications.yaml"
                        )
                        with open(apps_yaml_dest, "w") as f:
                            f.write(apps_yaml)
            finally:
                import ramble.workspace

                ramble.workspace.deactivate()
                shutil.rmtree(ws_dir, ignore_errors=True)


def generate_tutorial_data_js(docs_src_dir):
    """Compile tutorial paths and recipes into JavaScript data for the client."""
    paths_yaml = os.path.join(docs_src_dir, "tutorial_paths.yaml")
    out_dir = os.path.join(docs_src_dir, "_static")
    os.makedirs(out_dir, exist_ok=True)
    out_js = os.path.join(out_dir, "tutorial_data.js")

    data = {}
    if os.path.exists(paths_yaml):
        with open(paths_yaml, "r") as f:
            data = yaml.safe_load(f) or {}

    recipes, selectable_apps = load_all_recipes(docs_src_dir)
    data["recipes"] = recipes
    data["selectable_applications"] = selectable_apps

    with open(out_js, "w") as f:
        f.write("window.RAMBLE_TUTORIAL_DATA = " + json.dumps(data, indent=2) + ";\n")


def generate_all_tutorial_artifacts(app):
    """Sphinx hook to generate tutorial snippets and navigator data."""
    docs_src_dir = app.srcdir
    generate_tutorial_snippets(docs_src_dir)
    generate_tutorial_data_js(docs_src_dir)
