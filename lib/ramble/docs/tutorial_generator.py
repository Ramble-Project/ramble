# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
import html
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


class _FlowList(list):
    pass


class _TutDumper(yaml.SafeDumper):
    pass


_TutDumper.add_representer(
    _FlowList,
    lambda d, data: d.represent_sequence("tag:yaml.org,2002:seq", list(data), flow_style=True),
)


def _mark_flow_lists(obj, in_vars=False):
    if isinstance(obj, dict):
        return {
            k: _mark_flow_lists(v, in_vars=in_vars or (k == "variables"))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return _FlowList(obj) if in_vars else [_mark_flow_lists(x, False) for x in obj]
    return obj


_KEY_ORDER = [
    "variants",
    "env_vars",
    "internals",
    "variables",
    "zips",
    "modifiers",
    "success_criteria",
    "applications",
    "workloads",
    "experiments",
    "matrix",
    "software",
    "packages",
    "environments",
]


def _deep_merge(base, override, parent_key=None, pkg_name=None):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return copy.deepcopy(override)
    res = copy.deepcopy(base)
    added_new_key = False
    for k, v in override.items():
        if v is None:
            res.pop(k, None)
        elif k in res and isinstance(res[k], dict) and isinstance(v, dict):
            res[k] = _deep_merge(res[k], v, parent_key=k, pkg_name=pkg_name)
        else:
            if k not in res:
                added_new_key = True
            elif parent_key == "variables":
                res.pop(k, None)
            res[k] = copy.deepcopy(v)
    if added_new_key:
        if any(k in _KEY_ORDER for k in res):
            keys = sorted(
                res.keys(),
                key=lambda k: _KEY_ORDER.index(k) if k in _KEY_ORDER else 50,
            )
            res = {k: res[k] for k in keys}
        elif parent_key == "packages" and pkg_name and pkg_name in res:
            pkg_val = res.pop(pkg_name)
            res[pkg_name] = pkg_val
    return res


_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _sub_str(text, vars_dict):
    def _repl(m):
        key = m.group(1)
        return str(vars_dict[key]) if key in vars_dict else m.group(0)

    return _VAR_PATTERN.sub(_repl, text)


def _sub_vars(obj, vars_dict):
    if isinstance(obj, str):
        if obj.startswith("{") and obj.endswith("}") and obj[1:-1] in vars_dict:
            val = vars_dict[obj[1:-1]]
            if val != obj:
                return _sub_vars(val, vars_dict)
            return copy.deepcopy(val)
        return _sub_str(obj, vars_dict)
    if isinstance(obj, list):
        out = []
        for item in obj:
            if (
                isinstance(item, str)
                and item.startswith("{")
                and item.endswith("}")
                and item[1:-1] in vars_dict
            ):
                val = vars_dict[item[1:-1]]
                if isinstance(val, list):
                    out.extend(_sub_vars(val, vars_dict))
                else:
                    out.append(_sub_vars(val, vars_dict))
            else:
                out.append(_sub_vars(item, vars_dict))
        return out
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "<<":
                merged = _sub_vars(v, vars_dict)
                if isinstance(merged, dict):
                    out.update(merged)
                continue
            new_k = _sub_str(k, vars_dict) if isinstance(k, str) else k
            out[new_k] = _sub_vars(v, vars_dict)
        return out
    return copy.deepcopy(obj)


def _quote_cli_arg(arg):
    s = str(arg)
    return f"'{s}'" if any(c in s for c in ' {}[]"') else s


_RESERVED_APP_KEYS = {
    "name",
    "workload",
    "description",
    "workspace_name",
    "commands",
    "snippets",
    "vars",
}


def _expand_recipes(
    recipes, selectable_applications, snippet_templates, command_templates=None
):
    command_templates = command_templates or {}
    for recipe in recipes.values():
        apps = recipe.setdefault("apps", {})
        if not apps or set(apps).issubset(selectable_applications):
            ordered_apps = {}
            for app_id, base_app in selectable_applications.items():
                app_entry = apps.get(app_id) or {}
                for meta_key in ("name", "workload", "description"):
                    if meta_key in base_app:
                        app_entry.setdefault(meta_key, base_app[meta_key])
                ordered_apps[app_id] = app_entry
            recipe["apps"] = ordered_apps

        cmd_defaults = recipe.get("command_defaults", {})
        for app_id, app_info in recipe.get("apps", {}).items():
            base_app = selectable_applications.get(app_id, {})
            vars_dict = copy.deepcopy(command_templates)
            vars_dict.update(copy.deepcopy(base_app.get("vars", {})))
            vars_dict["app"] = app_id
            if "name" in app_info:
                vars_dict["name"] = app_info["name"]
            if "workload" in app_info:
                vars_dict["workload"] = app_info["workload"]
            if isinstance(app_info.get("vars"), dict):
                vars_dict.update(app_info["vars"])
            for k, v in app_info.items():
                if k not in _RESERVED_APP_KEYS:
                    vars_dict[k] = v

            if "workspace_name" in recipe and "workspace_name" not in app_info:
                app_info["workspace_name"] = _sub_str(str(recipe["workspace_name"]), vars_dict)
            elif isinstance(app_info.get("workspace_name"), str):
                app_info["workspace_name"] = _sub_str(app_info["workspace_name"], vars_dict)
            if "workspace_name" in app_info:
                vars_dict["ws_name"] = app_info["workspace_name"]

            raw_cmds = _sub_vars(
                app_info.get("commands", recipe.get("commands", [])), vars_dict
            )
            expanded_cmds = []
            for exp_step in raw_cmds:
                if cmd_defaults and isinstance(exp_step, dict):
                    merged_step = copy.deepcopy(cmd_defaults)
                    merged_step.update(exp_step)
                    exp_step = merged_step
                if exp_step.get("display") is True and exp_step.get("cmd"):
                    exp_step["display"] = "$ ramble " + " ".join(
                        _quote_cli_arg(a) for a in exp_step["cmd"]
                    )
                expanded_cmds.append(exp_step)
            if expanded_cmds or "commands" in app_info:
                app_info["commands"] = expanded_cmds

            recipe_snippets = recipe.get("snippets", {})
            app_snippets = app_info.get("snippets", {})
            if recipe_snippets or app_snippets:
                stage_names = list(dict.fromkeys(list(recipe_snippets) + list(app_snippets)))
                raw_stages = {}
                for s_name in stage_names:
                    r_stage = recipe_snippets.get(s_name)
                    a_stage = app_snippets.get(s_name)
                    if r_stage is not None and a_stage is not None:
                        raw_stages[s_name] = _deep_merge(
                            _sub_vars(r_stage, vars_dict),
                            _sub_vars(a_stage, vars_dict),
                            pkg_name=vars_dict.get("pkg_name"),
                        )
                    elif a_stage is not None:
                        raw_stages[s_name] = _sub_vars(a_stage, vars_dict)
                    else:
                        raw_stages[s_name] = _sub_vars(r_stage, vars_dict)

                resolved = {}

                def _resolve_stage(name):
                    if name in resolved:
                        return resolved[name]
                    if name not in raw_stages and name in snippet_templates:
                        return _sub_vars(snippet_templates[name], vars_dict)
                    stage_val = raw_stages[name]
                    if isinstance(stage_val, dict) and "extends" in stage_val:
                        parent_name = stage_val["extends"]
                        parent_dict = _resolve_stage(parent_name)
                        override_dict = {k: v for k, v in stage_val.items() if k != "extends"}
                        merged = _deep_merge(
                            parent_dict, override_dict, pkg_name=vars_dict.get("pkg_name")
                        )
                        resolved[name] = merged
                        return merged
                    resolved[name] = stage_val
                    return stage_val

                final_snippets = {}
                for s_name in stage_names:
                    val = _resolve_stage(s_name)
                    final_snippets[s_name] = (
                        _mark_flow_lists(val) if isinstance(val, dict) else val
                    )
                app_info["snippets"] = final_snippets


def _load_selectable_applications(docs_src_dir):
    selectable_apps_file = os.path.join(
        docs_src_dir, "tutorials", "selectable_applications.yaml"
    )
    if os.path.exists(selectable_apps_file):
        with open(selectable_apps_file, "r") as f:
            data = yaml.safe_load(f) or {}
            return (
                data.get("selectable_applications", {}),
                data.get("snippet_templates", {}),
                data.get("command_templates", {}),
                data.get("recipes", {}),
            )
    return {}, {}, {}, {}


def load_all_recipes(docs_src_dir):
    """Load all tutorial recipes and selectable applications."""
    selectable_applications, snippet_templates, command_templates, recipes = (
        _load_selectable_applications(docs_src_dir)
    )
    _expand_recipes(recipes, selectable_applications, snippet_templates, command_templates)
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
            commands = app_info.get("commands", [])
            needs_ws = any(
                step.get("use_workspace", True) and (step.get("cmd") or step.get("read_file"))
                for step in commands
            )
            ws_dir = (
                tempfile.mkdtemp(prefix=f"ramble_tut_{recipe_id}_{app_id}_") if needs_ws else None
            )
            try:
                # 0. Output custom named snippets if present
                custom_snippets = app_info.get("snippets", {})
                for snippet_name, snippet_content in custom_snippets.items():
                    snippet_path = os.path.join(
                        output_dir, f"{recipe_id}_{app_id}_{snippet_name}.yaml"
                    )
                    with open(snippet_path, "w") as f:
                        if isinstance(snippet_content, dict):
                            f.write(
                                yaml.dump(
                                    snippet_content, Dumper=_TutDumper, sort_keys=False, width=80
                                )
                            )
                        else:
                            f.write(str(snippet_content).strip() + "\n")

                # Execute each command in sandbox workspace
                for step in commands:
                    # Check if step has command_file
                    if step.get("command_file") and step.get("display"):
                        cmd_file_path = os.path.join(
                            output_dir, f"{recipe_id}_{app_id}_{step['command_file']}"
                        )
                        with open(cmd_file_path, "w") as f:
                            f.write(step["display"].strip() + "\n")

                    # Check if step is reading a file rather than running a command
                    if step.get("read_file") and ws_dir:
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
                        arg.replace("{ws}", ws_dir) if (isinstance(arg, str) and ws_dir) else arg
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
                        if (
                            use_workspace
                            and ws_dir
                            and not (cmd_name == "workspace" and sub_args and sub_args[0] == "create")
                        ):
                            full_exec_cmd.extend(["-D", ws_dir])
                        full_exec_cmd.extend(cmd)

                        captured_out = _run_cmd_for_snippet(full_exec_cmd, use_pty=use_pty)
                        if output_file:
                            ws_name = app_info.get("workspace_name") or (
                                recipe_id if recipe_id != "default" else app_id
                            )
                            sanitized = (
                                _sanitize_output(captured_out, ws_dir, ws_name)
                                if ws_dir
                                else captured_out
                            )
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
                    for step in commands
                    if step.get("display") and step.get("in_commands_sh", True)
                ]
                if display_cmds:
                    commands_path = os.path.join(
                        output_dir, f"{recipe_id}_{app_id}_commands.sh"
                    )
                    with open(commands_path, "w") as f:
                        f.write("\n".join(display_cmds) + "\n")

                # 2. Output generated ramble.yaml
                ramble_yaml_path = (
                    os.path.join(ws_dir, "configs", "ramble.yaml") if ws_dir else None
                )
                if ramble_yaml_path and os.path.exists(ramble_yaml_path):
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
                if ws_dir:
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

    tutorials = data.get("tutorials", {})
    tutorials_rst = os.path.join(docs_src_dir, "tutorials.rst")
    if tutorials and os.path.exists(tutorials_rst):
        with open(tutorials_rst, "r") as f:
            rst_text = f.read()
        for t_id, t_info in tutorials.items():
            doc_path = re.sub(r"\.html$", "", str(t_info.get("url", "")))
            if doc_path and doc_path not in rst_text:
                raise ValueError(
                    f"Tutorial '{t_id}' ({doc_path}) in tutorial_paths.yaml is missing from tutorials.rst"
                )

    goals = data.get("goals", {})
    if goals and tutorials:

        def _goal_avg_weight(item):
            _, goal = item
            step_keys = goal.get("tutorials", [])
            if not step_keys:
                return 999.0
            weights = [tutorials.get(k, {}).get("order_rank", 999) for k in step_keys]
            return sum(weights) / len(weights)

        data["goals"] = dict(sorted(goals.items(), key=_goal_avg_weight))

    recipes, selectable_apps = load_all_recipes(docs_src_dir)
    sel_summary = {
        k: {"name": v.get("name", k), "workload": v.get("workload", "")}
        for k, v in selectable_apps.items()
    }
    client_recipes = {}
    for r_id, r in recipes.items():
        if r_id in tutorials and r.get("workspace_name"):
            ws_tpl = r["workspace_name"]
            if ws_tpl != tutorials[r_id].get("default_workspace_name"):
                tutorials[r_id]["static_workspace_name"] = ws_tpl
        if "apps" in r and set(r["apps"]).issubset(selectable_apps):
            r_apps = {
                k: {"name": v.get("name", k), "workload": v.get("workload", "")}
                for k, v in r["apps"].items()
            }
            if r_apps != sel_summary:
                client_recipes[r_id] = {"apps": r_apps}
    if client_recipes:
        data["recipes"] = client_recipes
    data["selectable_applications"] = {
        k: {mk: mv for mk, mv in v.items() if mk not in ("vars", "foms")}
        for k, v in selectable_apps.items()
    }

    with open(out_js, "w") as f:
        f.write("window.RAMBLE_TUTORIAL_DATA = " + json.dumps(data, indent=2) + ";\n")

    generate_tutorial_navigator_html(docs_src_dir, data)


def generate_tutorial_navigator_html(docs_src_dir, data):
    """Pre-render the static HTML skeleton for the interactive tutorial navigator."""
    gen_dir = os.path.join(docs_src_dir, "_generated")
    os.makedirs(gen_dir, exist_ok=True)
    out_html = os.path.join(gen_dir, "tutorial_navigator.html")

    goals = data.get("goals", {})
    selectable_apps = data.get("selectable_applications", {})

    goal_items_html = []
    for key, goal in goals.items():
        esc_key = html.escape(str(key))
        esc_icon = html.escape(str(goal.get("icon", "📌")))
        esc_title = html.escape(str(goal.get("title", key)))
        esc_desc = html.escape(str(goal.get("description", "")))
        num_steps = len(goal.get("tutorials", []))
        goal_items_html.append(
            f'      <div class="tn-goal-item" data-goal-key="{esc_key}" '
            f'tabindex="0" role="checkbox" aria-checked="false">\n'
            f'        <div class="tn-goal-checkbox">\n'
            f'          <input type="checkbox" tabindex="-1" aria-hidden="true" />\n'
            f"        </div>\n"
            f'        <div class="tn-goal-content">\n'
            f'          <div class="tn-goal-header">\n'
            f'            <span class="tn-goal-icon">{esc_icon}</span>\n'
            f'            <span class="tn-goal-title">{esc_title}</span>\n'
            f'            <span class="tn-badge tn-badge-steps">{num_steps} steps</span>\n'
            f"          </div>\n"
            f'          <div class="tn-goal-desc">{esc_desc}</div>\n'
            f"        </div>\n"
            f"      </div>"
        )

    app_cards_html = []
    for key, app in selectable_apps.items():
        esc_key = html.escape(str(key))
        esc_name = html.escape(str(app.get("name", key)))
        esc_workload = html.escape(str(app.get("workload", "default")))
        esc_desc = html.escape(str(app.get("description", "")))
        app_cards_html.append(
            f'      <div class="tn-app-pref-card" data-app="{esc_key}" '
            f'tabindex="0" role="radio" aria-checked="false">\n'
            f'        <div class="tn-app-pref-radio">\n'
            f'          <input type="radio" name="tn-pref-app" value="{esc_key}" tabindex="-1" />\n'
            f"        </div>\n"
            f'        <div class="tn-app-pref-info">\n'
            f'          <div class="tn-app-pref-title-row">\n'
            f'            <span class="tn-app-pref-name">{esc_name}</span>\n'
            f'            <span class="tn-badge tn-badge-time">Workload: {esc_workload}</span>\n'
            f"          </div>\n"
            f'          <div class="tn-app-pref-desc">{esc_desc}</div>\n'
            f"        </div>\n"
            f"      </div>"
        )

    goals_block = "\n".join(goal_items_html)
    apps_block = "\n".join(app_cards_html)

    navigator_html = f"""<div id="tutorial-navigator-app">
  <div class="tn-container">
    <div class="tn-header">
      <h3 class="tn-title">🎯 Interactive Tutorial Navigator</h3>
      <p class="tn-subtitle">
        Follow a guided learning pathway based on your end goals, or browse tutorials individually in stand-alone mode.
      </p>
    </div>

    <div class="tn-mode-section">
      <div class="tn-section-heading">
        <span class="tn-heading-text">Choose How You Want to Explore</span>
      </div>
      <div class="tn-mode-grid" id="tn-mode-grid" role="radiogroup" aria-label="Tutorial Navigation Mode">
        <div class="tn-mode-card active" data-mode="pathway" tabindex="0" role="radio" aria-checked="true">
          <div class="tn-mode-radio">
            <input type="radio" name="tn-mode" value="pathway" tabindex="-1" checked />
          </div>
          <div class="tn-mode-info">
            <div class="tn-mode-title-row">
              <span class="tn-mode-name">🧭 Learning Pathways</span>
              <span class="tn-badge tn-badge-steps">Guided Curriculum</span>
            </div>
            <div class="tn-mode-desc">
              Select one or more end goals to generate a customized, multi-step roadmap that reuses workspaces and repositories across steps.
            </div>
          </div>
        </div>
        <div class="tn-mode-card" data-mode="standalone" tabindex="0" role="radio" aria-checked="false">
          <div class="tn-mode-radio">
            <input type="radio" name="tn-mode" value="standalone" tabindex="-1" />
          </div>
          <div class="tn-mode-info">
            <div class="tn-mode-title-row">
              <span class="tn-mode-name">📄 Stand-Alone Tutorials</span>
              <span class="tn-badge tn-badge-steps">Self-Contained Steps</span>
            </div>
            <div class="tn-mode-desc">
              Browse and open any tutorial directly without an active learning pathway. Instructions show self-contained setup and cleanup without pathway notices.
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="tn-goals-section" id="tn-goals-section">
      <div class="tn-section-heading">
        <span class="tn-heading-text" id="tn-goals-heading">1. Choose Your End Goals (Select one or more)</span>
        <div class="tn-goal-actions">
          <button type="button" class="tn-btn tn-btn-sm" id="tn-select-all-goals">Select All</button>
          <button type="button" class="tn-btn tn-btn-sm" id="tn-clear-goals">Clear All</button>
        </div>
      </div>
      <div class="tn-goals-list" id="tn-goals-list">
{goals_block}
      </div>
    </div>

    <div class="tn-summary-bar" id="tn-summary-bar"></div>

    <div class="tn-apps-section">
      <div class="tn-section-heading">
        <span class="tn-heading-text" id="tn-apps-heading">2. Choose Preferred Application (for multi-application tutorials)</span>
      </div>
      <p class="tn-apps-desc">
        Some tutorials (such as Scaling Studies) support multiple application workloads. Select your preferred application to follow throughout those tutorials:
      </p>
      <div class="tn-apps-grid" id="tn-apps-grid">
{apps_block}
      </div>
    </div>

    <div class="tn-dry-run-section">
      <div class="tn-section-heading">
        <span class="tn-heading-text" id="tn-dry-run-heading">3. Execution Mode (Dry-Run vs. Full Execution)</span>
      </div>
      <div id="tn-dry-run-pref-container">
        <div class="tn-dry-run-pref-card" tabindex="0" role="checkbox" aria-checked="false">
          <div class="tn-dry-run-pref-checkbox">
            <input type="checkbox" class="tn-dry-run-checkbox" tabindex="-1" aria-hidden="true" />
          </div>
          <div class="tn-dry-run-pref-info">
            <div class="tn-dry-run-pref-title-row">
              <span class="tn-dry-run-pref-name">🧪 Enable Dry-Run Mode (<code>--dry-run</code>)</span>
              <span class="tn-badge tn-badge-time">⚡ Faster Walkthrough</span>
            </div>
            <div class="tn-dry-run-pref-desc">
              Runs <code>ramble workspace setup --dry-run</code> to generate experiment directories and scripts without downloading inputs or compiling software. Skips executing (<code>ramble on</code>) and analyzing (<code>ramble workspace analyze</code>) experiments, guides you through exploring the generated experiment directories, and displays example outputs for reference.
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="tn-pathway-section">
      <div class="tn-section-heading">
        <span class="tn-heading-text" id="tn-pathway-heading">4. Recommended Learning Path</span>
      </div>
      <div class="tn-pathway-list" id="tn-pathway-list"></div>
    </div>
  </div>
</div>
"""
    with open(out_html, "w") as f:
        f.write(navigator_html)


def generate_all_tutorial_artifacts(app):
    """Sphinx hook to generate tutorial snippets and navigator data."""
    docs_src_dir = app.srcdir
    generate_tutorial_snippets(docs_src_dir)
    generate_tutorial_data_js(docs_src_dir)


def _get_app_template_defaults(selectable_apps):
    defaults = {}
    for app_id, app_info in selectable_apps.items():
        app_vars = {
            k: str(v)
            for k, v in app_info.get("vars", {}).items()
            if isinstance(v, (str, int, float))
        }
        app_vars.update(
            {
                "app": app_id,
                "app_upper": app_info.get("name", app_id.upper()),
                "workload": app_info.get("workload", ""),
            }
        )
        defaults[app_id] = app_vars
    return defaults


def _parse_app_overrides(raw_opt):
    if not raw_opt:
        return {}
    overrides = {}
    for part in raw_opt.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            overrides[k.strip()] = v.strip()
        else:
            overrides["val"] = part
    return overrides


_REPO_CREATE_LINES = [
    "Ramble Repositories",
    "===================",
    "",
    ".. container:: tn-repo-create",
    "",
    "   Before writing our definitions, we will create a repository to house",
    "   the application definition. Repositories in Ramble can house any object type,",
    "   and are not limited to only those in this tutorial.",
    "",
    "   The ``ramble repo`` command is used to manage object repositories in Ramble. To",
    "   create a new repository, execute the following:",
    "",
    "   .. code-block:: console",
    "",
    "       $ ramble repo create tutorial-repo",
    "",
    "   This will create a new directory named ``tutorial-repo`` in your current",
    "   directory. Inside, directories will exist for each of the object types, such as",
    "   ``applications/`` and ``package_managers/`` (e.g.,",
    "   ``tutorial-repo/applications/hostname/application.py``), or without object",
    "   subdirectories if created with ``ramble repo create tutorial-repo -d \"\"``.",
    "",
    "   Object files within the repository are named after the object type they",
    "   represent (e.g., ``application.py``, ``base_application.py``, ``modifier.py``,",
    "   ``package_manager.py``, ``workflow_manager.py``, ``system.py``, ``platform.py``,",
    "   ``utility.py``).",
    "",
    "   Once your repository is created, register it with Ramble using:",
    "",
    "   .. code-block:: console",
    "",
    "       $ ramble repo add tutorial-repo",
    "",
    "   .. note::",
    "      Ramble comes with a default ``builtin`` repository. Adding new",
    "      repositories gives them higher precedence than existing repositories.",
    "      Each repository has a namespace that can be used to refer to specific",
    "      object definitions (e.g., ``tutorial-repo.hostname``, ``builtin.app.wrf@4.2``).",
    "",
]

_REPO_CLEANUP_LINES = [
    ".. container:: tn-repo-cleanup",
    "",
    "   You are also free to delete the ``tutorial-repo`` repository, but make sure you",
    "   unregister it from your list of repositories using the ``ramble repo rm``",
    "   command:",
    "",
    "   .. code-block:: console",
    "",
    "       $ ramble repo rm tutorial-repo",
    "       $ rm -rf tutorial-repo",
    "",
]


def register_tutorial_directives(sphinx):
    """Register custom Sphinx directives for multi-application tutorials."""
    from docutils import nodes
    from docutils.parsers.rst import directives
    from docutils.statemachine import StringList
    from sphinx.util.docutils import SphinxDirective
    from sphinx.util.nodes import nested_parse_with_titles

    selectable_apps, _, _, _ = _load_selectable_applications(
        os.path.dirname(os.path.abspath(__file__))
    )
    app_template_defaults = _get_app_template_defaults(selectable_apps)
    default_apps_csv = ",".join(selectable_apps) or "wrf,gromacs,hpl"
    app_foms = {k: v.get("foms", []) for k, v in selectable_apps.items()}
    app_option_spec = {k: directives.unchanged for k in selectable_apps}

    class _TutorialBaseDirective(SphinxDirective):
        def _get_apps(self):
            return [
                a.strip()
                for a in self.options.get("apps", default_apps_csv).split(",")
                if a.strip()
            ]

        def _parse_rst_lines(self, lines):
            node = nodes.Element()
            source = self.state.document.current_source
            nested_parse_with_titles(
                self.state, StringList(lines, source=source), node
            )
            return node.children

    class TutorialSnippetDirective(_TutorialBaseDirective):
        required_arguments = 2
        optional_arguments = 0
        has_content = False
        option_spec = {
            "language": directives.unchanged,
            "alt-yaml": directives.unchanged,
            "alt-text": directives.unchanged,
            "apps": directives.unchanged,
        }

        def run(self):
            recipe = self.arguments[0]
            suffix = self.arguments[1]
            lang = self.options.get("language")
            if not lang:
                lang = (
                    "YAML" if suffix.endswith(".yaml") or suffix.endswith(".yml") else "console"
                )
            alt_yaml = self.options.get("alt-yaml")
            alt_text = self.options.get(
                "alt-text",
                "Alternatively, you can edit the ``configs/ramble.yaml`` file "
                "directly to match the following configuration:",
            )
            apps = self._get_apps()
            lines = []
            for app in apps:
                lines.extend(
                    [
                        f".. container:: tn-app-variant tn-app-{app}",
                        "",
                        f"   .. literalinclude:: /_generated/snippets/{recipe}_{app}_{suffix}",
                        f"      :language: {lang}",
                        "",
                    ]
                )
                if alt_yaml:
                    lines.extend(
                        [
                            f"   {alt_text}",
                            "",
                            f"   .. literalinclude:: /_generated/snippets/{recipe}_{app}_{alt_yaml}",
                            "      :language: YAML",
                            "",
                        ]
                    )
            return self._parse_rst_lines(lines)

    class TutorialAppTemplateDirective(_TutorialBaseDirective):
        required_arguments = 0
        optional_arguments = 0
        has_content = True
        option_spec = {
            **app_option_spec,
            "apps": directives.unchanged,
        }

        def run(self):
            apps = self._get_apps()
            lines = []
            for app in apps:
                vars_dict = dict(app_template_defaults.get(app, {"app": app}))
                vars_dict.update(_parse_app_overrides(self.options.get(app)))
                lines.append(f".. container:: tn-app-variant tn-app-{app}")
                lines.append("")
                for content_line in self.content:
                    has_placeholder = bool(_VAR_PATTERN.search(content_line))
                    rendered = re.sub(
                        r"\{([a-zA-Z0-9_]+)\}",
                        lambda m, vd=vars_dict: vd.get(m.group(1), m.group(0)),
                        content_line,
                    )
                    if has_placeholder and not rendered.strip():
                        continue
                    lines.append(f"   {rendered}" if rendered else "")
                lines.append("")
            return self._parse_rst_lines(lines)

    class TutorialExecuteDirective(_TutorialBaseDirective):
        required_arguments = 1
        optional_arguments = 0
        has_content = True
        option_spec = {
            "timing-note": directives.unchanged,
            "no-timing-note": directives.flag,
            "dry-run-cmds": directives.unchanged,
            "results-text": directives.unchanged,
            "include-foms": directives.flag,
            "single": directives.flag,
            "apps": directives.unchanged,
            "package-manager": directives.unchanged,
            "concretize": directives.flag,
            "no-analyze": directives.flag,
            **app_option_spec,
        }

        def run(self):
            ws = self.arguments[0]
            is_single = "single" in self.options
            no_analyze = "no-analyze" in self.options
            concretize = "concretize" in self.options
            no_timing_note = "no-timing-note" in self.options
            pkg_man = self.options.get("package-manager", "spack").strip().lower()
            apps = self._get_apps()
            timing_note = self.options.get(
                "timing-note",
                "When not running in dry-run mode, ``ramble workspace setup`` will build "
                "the required software stack from source if it is not already installed on "
                "your system and download any required workload input files, while "
                "``ramble on`` executes the configured benchmark experiments.",
            )
            include_foms = "include-foms" in self.options
            default_results_text = (
                "Examining the experiment run directories shows the output of the executed "
                "experiments."
                if no_analyze
                else "This creates a ``results.latest.txt`` file in the root of the workspace "
                "containing the extracted figures of merit:"
            )
            results_text = self.options.get("results-text", default_results_text)
            default_dry_cmd = (
                f"ls -la $RAMBLE_ROOT/var/ramble/workspaces/{ws}/experiments/"
                if is_single
                else f"ls -la $RAMBLE_ROOT/var/ramble/workspaces/{ws}_{{app}}/experiments/{{app}}/{{workload}}/"
            )
            raw_cmds = self.options.get("dry-run-cmds", default_dry_cmd)
            dry_cmds = [c.strip() for c in raw_cmds.split(";") if c.strip()]

            lines = [".. container:: tn-full-run-only", ""]
            if pkg_man == "spack":
                lines.extend(
                    [
                        "   .. note::",
                        "      By default, the experiments in this tutorial use `Spack <https://spack.io/>`_",
                        "      (configured via ``package_manager: spack``) to build and install the required",
                        "      software stack. ``spack`` can either be installed in your ``PATH``, or Ramble",
                        "      will automatically bootstrap it for you.",
                        "",
                    ]
                )
            if not no_timing_note:
                lines.extend(
                    [
                        "   .. note::",
                        f"      {timing_note}",
                        "      You can optionally enable **Dry-Run Mode** at the top of this tutorial or pass",
                        "      ``--dry-run`` to ``ramble workspace setup`` to quickly generate and inspect the",
                        "      experiment directories without building software or running the experiments.",
                        "",
                    ]
                )
            action_desc = (
                "To set up and execute the experiments:"
                if no_analyze
                else "To set up, execute, and analyze the experiments:"
            )
            lines.extend(
                [
                    f"   {action_desc}",
                    "",
                    "   .. code-block:: console",
                    "",
                ]
            )
            if concretize:
                lines.append("       $ ramble workspace concretize")
            lines.append("       $ ramble workspace setup")
            lines.append("       $ ramble on")
            if not no_analyze:
                lines.append("       $ ramble workspace analyze")
            lines.append("")

            if self.content:
                for content_line in self.content:
                    lines.append(f"   {content_line}" if content_line else "")
                lines.append("")
            lines.extend(
                [
                    f"   {results_text}",
                    "",
                    ".. container:: tn-dry-run-only",
                    "",
                    "   With **Dry-Run Mode** enabled, set up the workspace using ``--dry-run``:",
                    "",
                    "   .. code-block:: console",
                    "",
                ]
            )
            if concretize:
                lines.append("       $ ramble workspace concretize")
            lines.append("       $ ramble workspace setup --dry-run")
            lines.append("")
            skip_desc = (
                "   Because we are running in dry-run mode, we do **not** execute ``ramble on``."
                if no_analyze
                else "   Because we are running in dry-run mode, we do **not** execute ``ramble on`` or\n"
                "   ``ramble workspace analyze``."
            )
            lines.extend(
                [
                    skip_desc,
                    "   Instead, explore the generated workspace directories and rendered",
                    "   ``execute_experiment`` scripts:",
                    "",
                ]
            )
            if is_single:
                lines.extend(
                    [
                        "   .. code-block:: console",
                        "",
                    ]
                )
                for cmd in dry_cmds:
                    lines.append(f"       $ {cmd}")
            else:
                lines.append("   .. tutorial-app-template::")
                for app_opt in selectable_apps:
                    if app_opt in self.options:
                        lines.append(f"      :{app_opt}: {self.options[app_opt]}")
                lines.extend(
                    [
                        "",
                        "      .. code-block:: console",
                        "",
                    ]
                )
                for cmd in dry_cmds:
                    lines.append(f"          $ {cmd}")
            run_clause = (
                "In a full run where ``ramble on`` is executed,"
                if no_analyze
                else "In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,"
            )
            lines.extend(
                [
                    "",
                    "   **Example Output (Full Run):**",
                    "",
                    f"   {run_clause}",
                    f"   {results_text[0].lower() + results_text[1:] if results_text else ''}",
                    "",
                ]
            )
            if include_foms:
                if is_single:
                    for app in apps:
                        for fom_line in app_foms.get(app, []):
                            lines.append(fom_line)
                    lines.append("")
                else:
                    for app in apps:
                        fom_lines = app_foms.get(app, [])
                        if not fom_lines:
                            continue
                        lines.append(f".. container:: tn-app-variant tn-app-{app}")
                        lines.append("")
                        for fom_line in fom_lines:
                            lines.append(f"   {fom_line}")
                        lines.append("")
            return self._parse_rst_lines(lines)

    class TutorialWorkspaceCreateDirective(_TutorialBaseDirective):
        required_arguments = 1
        optional_arguments = 0
        has_content = True
        option_spec = {
            "separate-activate": directives.flag,
            "single": directives.flag,
            "dir": directives.flag,
            "no-activate": directives.flag,
            "activate-only": directives.flag,
            "apps": directives.unchanged,
        }

        def run(self):
            ws_prefix = self.arguments[0]
            separate_activate = "separate-activate" in self.options
            is_single = "single" in self.options
            is_dir = "dir" in self.options
            no_activate = "no-activate" in self.options
            activate_only = "activate-only" in self.options
            apps = self._get_apps()
            lines = [".. container:: tn-workspace-create", ""]
            if self.content:
                for content_line in self.content:
                    lines.append(f"   {content_line}" if content_line else "")
                lines.append("")
            else:
                default_prompt = (
                    "   Ensure your workspace is activated before continuing:"
                    if activate_only
                    else "   First, create and activate a new workspace for this tutorial:"
                )
                lines.extend([default_prompt, ""])

            def _emit_ws_cmds(ws_name, indent):
                if activate_only:
                    return [
                        f"{indent}.. code-block:: console",
                        "",
                        f"{indent}    $ ramble workspace activate {ws_name}",
                        "",
                    ]
                if is_dir:
                    act_flag = "" if no_activate else " -a"
                    return [
                        f"{indent}.. code-block:: console",
                        "",
                        f"{indent}    $ ramble workspace create -d {ws_name}{act_flag}",
                        "",
                    ]
                if separate_activate:
                    return [
                        f"{indent}.. code-block:: console",
                        "",
                        f"{indent}    $ ramble workspace create {ws_name}",
                        f"{indent}    $ ramble workspace activate {ws_name}",
                        "",
                    ]
                act_flag = "" if no_activate else "-a "
                return [
                    f"{indent}.. code-block:: console",
                    "",
                    f"{indent}    $ ramble workspace create {act_flag}{ws_name}",
                    "",
                ]

            if is_single or is_dir:
                lines.extend(_emit_ws_cmds(ws_prefix, "   "))
            else:
                for app in apps:
                    lines.append(f"   .. container:: tn-app-variant tn-app-{app}")
                    lines.append("")
                    lines.extend(_emit_ws_cmds(f"{ws_prefix}_{app}", "      "))
            return self._parse_rst_lines(lines)

    class TutorialWorkspaceCleanupDirective(_TutorialBaseDirective):
        required_arguments = 1
        optional_arguments = 10
        has_content = True
        option_spec = {
            "apps": directives.unchanged,
            "single": directives.flag,
            "dir": directives.flag,
            "no-deactivate": directives.flag,
        }

        def run(self):
            ws_names = list(self.arguments)
            ws_prefix = ws_names[0]
            is_single = "single" in self.options
            is_dir = "dir" in self.options
            no_deactivate = "no-deactivate" in self.options
            apps = self._get_apps()
            lines = [".. container:: tn-workspace-cleanup", ""]
            if self.content:
                for content_line in self.content:
                    lines.append(f"   {content_line}" if content_line else "")
                lines.append("")
            if is_dir:
                ws_joined = " ".join(ws_names)
                if no_deactivate:
                    lines.extend(
                        [
                            "   To clean up the tutorial workspace:",
                            "",
                            "   .. code-block:: console",
                            "",
                            f"       $ rm -rf {ws_joined}",
                            "",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            "   Deactivate and remove the workspace:",
                            "",
                            "   .. code-block:: console",
                            "",
                            "       $ ramble workspace deactivate",
                            f"       $ rm -rf {ws_joined}",
                            "",
                        ]
                    )
                return self._parse_rst_lines(lines)

            if not no_deactivate:
                lines.extend(
                    [
                        "   Deactivate the workspace:",
                        "",
                        "   .. code-block:: console",
                        "",
                        "       $ ramble workspace deactivate",
                        "",
                    ]
                )
            lines.extend(
                [
                    "   To completely remove the workspace:",
                    "",
                ]
            )
            if is_single:
                lines.extend(
                    [
                        "   .. code-block:: console",
                        "",
                    ]
                )
                for ws_n in ws_names:
                    lines.append(f"       $ ramble workspace remove {ws_n}")
                lines.append("")
            else:
                for app in apps:
                    lines.extend(
                        [
                            f"   .. container:: tn-app-variant tn-app-{app}",
                            "",
                            "      .. code-block:: console",
                            "",
                            f"          $ ramble workspace remove {ws_prefix}_{app}",
                            "",
                        ]
                    )
            return self._parse_rst_lines(lines)

    class TutorialRepoCreateDirective(_TutorialBaseDirective):
        required_arguments = 0
        optional_arguments = 0
        has_content = False

        def run(self):
            return self._parse_rst_lines(_REPO_CREATE_LINES)

    class TutorialRepoCleanupDirective(_TutorialBaseDirective):
        required_arguments = 0
        optional_arguments = 0
        has_content = False

        def run(self):
            return self._parse_rst_lines(_REPO_CLEANUP_LINES)

    class TutorialHeaderDirective(_TutorialBaseDirective):
        required_arguments = 0
        optional_arguments = 1
        has_content = False

        def run(self):
            if self.arguments:
                recipe = html.escape(self.arguments[0])
                raw_html = f'<div class="tn-app-switcher" data-recipe="{recipe}"></div>'
            else:
                raw_html = '<div class="tn-ws-prompt"></div>'
            return [nodes.raw("", raw_html, format="html")]

    sphinx.add_directive("tutorial-snippet", TutorialSnippetDirective)
    sphinx.add_directive("tutorial-app-template", TutorialAppTemplateDirective)
    sphinx.add_directive("tutorial-execute", TutorialExecuteDirective)
    sphinx.add_directive("tutorial-workspace-create", TutorialWorkspaceCreateDirective)
    sphinx.add_directive("tutorial-workspace-cleanup", TutorialWorkspaceCleanupDirective)
    sphinx.add_directive("tutorial-repo-create", TutorialRepoCreateDirective)
    sphinx.add_directive("tutorial-repo-cleanup", TutorialRepoCleanupDirective)
    sphinx.add_directive("tutorial-header", TutorialHeaderDirective)

