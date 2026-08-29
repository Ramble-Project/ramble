# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import datetime
import os
import re
from enum import Enum
from typing import Dict, List

import llnl.util.filesystem as fs

import ramble.config
import ramble.expander
import ramble.repository
import ramble.util.path
from ramble.keywords import keywords
from ramble.util.file_util import create_symlink
from ramble.util.foms import BetterDirection, FomType, SummaryFoms
from ramble.util.logger import logger
from ramble.util.module_utils import import_pandas

import spack.util.spack_yaml as syaml

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
except ModuleNotFoundError:
    logger.die("matplotlib was not found. Ensure requirements.txt are installed.")


class ReportVars(Enum):
    APP_NAME = "application_name"
    BETTER_DIRECTION = "better_direction"
    CONTEXT_NAME = "context_name"
    EXP_NAME = "experiment_name"
    EXP_NS = "experiment_namespace"
    FOM_NAME = "fom_name"
    FOM_ORIGIN = "fom_origin"
    FOM_ORIGIN_TYPE = "fom_origin_type"
    FOM_UNITS = "fom_units"
    FOM_VALUE = "fom_value"
    FOM_VALUE_MIN = "fom_value_min"
    FOM_VALUE_MAX = "fom_value_max"
    IDEAL_PERF_VALUE = "ideal_perf_value"
    NORMALIZED_FOM_VALUE = "normalized_fom_value"
    SERIES = "series"
    WL_NAME = "workload_name"
    WL_NS = "workload_namespace"


_FOM_DICT_MAPPING = {
    "name": ReportVars.FOM_NAME.value,
    "value": ReportVars.FOM_VALUE.value,
    "units": ReportVars.FOM_UNITS.value,
    "origin": ReportVars.FOM_ORIGIN.value,
    "origin_type": ReportVars.FOM_ORIGIN_TYPE.value,
}

# Core experiment metadata extracted for every DataFrame
_EXP_BASIC_VARS_MAPPING = {
    "experiment_name": ReportVars.EXP_NAME.value,
    "experiment_namespace": ReportVars.EXP_NS.value,
    "application_name": ReportVars.APP_NAME.value,
    "workload_name": ReportVars.WL_NAME.value,
    "workload_namespace": ReportVars.WL_NS.value,
}

_ADDITIONAL_VARS = {
    ReportVars.CONTEXT_NAME.value,
}

INVENTORY_FILENAME = "inventory.yaml"
OBJECT_NAMES = {}
for obj in ramble.repository.ObjectTypes:
    singular = ramble.repository.type_definitions[obj]["singular"]
    OBJECT_NAMES[singular] = obj.name


def to_numeric_if_possible(series):
    """Try to convert a Pandas series to numeric, or return the series unchanged."""
    pd = import_pandas()
    try:
        return pd.to_numeric(series)
    except (ValueError, TypeError):
        return series


def simplify_names(names):
    """Simplify a list of dot-separated names by stripping the longest common prefix
    and suffix parts.
    """
    if not names or len(names) <= 1:
        return names

    names = [str(name) for name in names]
    split_names = [name.split(".") for name in names]

    # Find longest common prefix of parts
    common_prefix = []
    min_len = min(len(parts) for parts in split_names)
    for i in range(min_len):
        part = split_names[0][i]
        if all(parts[i] == part for parts in split_names):
            common_prefix.append(part)
        else:
            break

    # Find longest common suffix of parts
    common_suffix = []
    remaining_min_len = min(len(parts) - len(common_prefix) for parts in split_names)
    for i in range(1, remaining_min_len + 1):
        part = split_names[0][-i]
        if all(parts[-i] == part for parts in split_names):
            common_suffix.insert(0, part)
        else:
            break

    simplified = []
    for parts in split_names:
        end_idx = -len(common_suffix) if common_suffix else len(parts)
        simplified_parts = parts[len(common_prefix) : end_idx]
        if not simplified_parts:
            return names
        simplified.append(".".join(simplified_parts))

    return simplified


def clean_redundant_prefixes(name, application_name, workload_name):
    """Strip application and workload names from a name string,
    handling case, dots, underscores, and hyphens.
    """
    if not name:
        return name

    app_norm = (application_name or "").replace("-", "_").replace(".", "_").lower()
    wl_norm = (workload_name or "").replace("-", "_").replace(".", "_").lower()

    name_lower = name.lower().replace("-", "_").replace(".", "_")

    prefixes = sorted([app_norm, wl_norm], key=len, reverse=True)

    modified = True
    while modified:
        modified = False
        for prefix_norm in prefixes:
            if not prefix_norm:
                continue
            matched = False
            for sep in ["_", "."]:
                full_prefix = prefix_norm + sep
                if name_lower.startswith(full_prefix):
                    name = name[len(full_prefix) :]
                    name_lower = name_lower[len(full_prefix) :]
                    matched = True
                    break
            if not matched:
                if name_lower.startswith(prefix_norm):
                    name = name[len(prefix_norm) :]
                    name_lower = name_lower[len(prefix_norm) :]
                    matched = True

            if matched:
                modified = True
                break

    return name


def get_common_stripped_prefix(original_values, simplified_values):
    """Find the longest common prefix stripped from original_values to get simplified_values."""
    if not original_values or not simplified_values:
        return ""

    prefixes = []
    for orig, simp in zip(original_values, simplified_values):
        orig_str = str(orig)
        simp_str = str(simp)
        if simp_str in orig_str:
            idx = orig_str.find(simp_str)
            prefixes.append(orig_str[:idx])
        else:
            prefixes.append("")

    if not prefixes:
        return ""
    common = prefixes[0]
    for p in prefixes[1:]:
        while not p.startswith(common):
            common = common[:-1]
            if not common:
                return ""
    return common


def simplify_experiment_names(df, index_col=None):
    """Simplify the index or a column of a dataframe by stripping redundant
    application/workload names and common prefixes/suffixes.
    """
    # Extract values to simplify
    if index_col is None:
        original_values = df.index.tolist()
    else:
        original_values = df[index_col].tolist()

    simplified_values = []

    # 1. Row-by-row clean redundant prefixes
    app_col = ReportVars.APP_NAME.value
    wl_col = ReportVars.WL_NAME.value
    app_names = df[app_col].tolist() if app_col in df.columns else [""] * len(df)
    wl_names = df[wl_col].tolist() if wl_col in df.columns else [""] * len(df)

    for val, app_name, wl_name in zip(original_values, app_names, wl_names):
        parts = str(val).split(".")
        cleaned_parts = []
        for part in parts:
            cleaned_part = clean_redundant_prefixes(part, app_name, wl_name)
            if cleaned_part:
                cleaned_parts.append(cleaned_part)

        simplified_val = ".".join(cleaned_parts) if cleaned_parts else str(val)
        simplified_values.append(simplified_val)

    # 2. Strip common prefix and suffix from the entire list of simplified values
    final_values = simplify_names(simplified_values)

    common_prefix = get_common_stripped_prefix(original_values, final_values)

    # Check if simplification introduced collisions/reduced uniqueness
    if len(set(final_values)) < len(set(original_values)):
        logger.debug("Simplification introduced name collisions. Falling back to original values.")
        final_values = original_values
        common_prefix = ""

    # Update the dataframe
    if index_col is None:
        df.index = final_values
    else:
        df[index_col] = final_values

    return df, common_prefix


def get_direction_suffix(self):
    if self == BetterDirection.HIGHER:
        return " (Higher is Better)"
    if self == BetterDirection.LOWER:
        return " (Lower is Better)"
    else:
        return ""


def is_repeat_child(experiment):
    if int(experiment["RAMBLE_VARIABLES"][keywords.repeat_index]) > 0:
        return True
    else:
        return False


def is_key_to_skip(key_name: str):
    """Check if a results dict key should be skipped for indexing and analysis.

    The purpose of this is to ignore non-variables and reduce clutter in the
    results index. Some values in the results index, like paths and commands,
    have limited utility for analysis or are derived from variables that are
    available separately.
    """
    keys_to_skip = {
        keywords.batch_submit,
        keywords.log_file,
        "command",
        "execute_experiment",
        "experiment_hash",
        "experiment_status",
        "name",
        "RAMBLE_STATUS",
        "CONTEXTS",
        "RAMBLE_VARIABLES",
        "RAMBLE_RAW_VARIABLES",
        "SOFTWARE",
        "TAGS",
        "VARIANTS",
        "EXPERIMENT_CHAIN",
        "SUCCESS_CRITERIA",
    }

    skip = False
    if key_name in keys_to_skip:
        skip = True
        return skip
    elif key_name.endswith(("dir", "path")):
        skip = True
    return skip


def filter_exp_results(experiments: list):
    """Filters a list of experiment results to remove failed experiments and
    duplicate data.

    When repeats are used, this removes individual repeats and returns only the
    summary statistics.
    """
    filtered_exps = []
    skip_exps = []

    for exp in experiments:
        if exp["name"] in skip_exps or is_repeat_child(exp):
            logger.debug(f"Skipping import of experiment {exp['name']}")
            continue

        elif exp["RAMBLE_STATUS"] != "SUCCESS":
            continue
        else:
            logger.debug(f"Importing experiment {exp['name']}")
            # For repeat experiments, use summary stats from base exp and skip repeats
            # Repeats are sequenced after base exp

            if exp.get("N_REPEATS", 0) > 0:
                # Generate repeat experiment names in order to skip them explicitly
                exp_name = exp["name"]
                for n in range(1, exp["N_REPEATS"] + 1):
                    if ".chain" in exp_name:
                        insert_idx = exp_name.index(".chain")
                        repeat_exp_name = exp_name[:insert_idx] + f".{n}" + exp_name[insert_idx:]
                        skip_exps.append(repeat_exp_name)
                    else:
                        skip_exps.append(exp_name + f".{n}")
            filtered_exps.append(exp)

    return filtered_exps


def generate_result_index(experiments: list, all_vars=False, where_query=None):
    """Creates an index from the results in the list of experiments

    Index format is::

        {
            "applications": {
                application_name: {
                    workload: {
                        "Contexts": set(),
                        "FOMs": set(),
                        "Template Variables": set(),
                    }
                }
            }
            "modifiers": {
                modifier_name: {
                    "Contexts": set(),
                    "FOMs": set(),
                }
            (all other object types)
        }
    """
    result_index: Dict[str, dict] = {}
    for obj_name in OBJECT_NAMES.values():
        result_index[obj_name] = {}

    template_patterns: Dict[str, dict] = {}
    # First unnest dictionaries
    for exp in experiments:
        if exp["application_name"] not in result_index["applications"]:
            result_index["applications"][exp["application_name"]] = {}
        app_dict = result_index["applications"][exp["application_name"]]

        if exp["workload_name"] not in app_dict:
            app_dict[exp["workload_name"]] = {
                "Contexts": set(),
                "FOMs": set(),
                "Template Variables": set(),
            }
        if exp["application_name"] not in template_patterns:
            template_patterns[exp["application_name"]] = {}
        if exp["workload_name"] not in template_patterns[exp["application_name"]]:
            template_patterns[exp["application_name"]][exp["workload_name"]] = set()

        if all_vars:
            if "All Variables" not in app_dict[exp["workload_name"]]:
                app_dict[exp["workload_name"]]["All Variables"] = set()
            for var_name in exp:
                if is_key_to_skip(var_name):
                    continue
                app_dict[exp["workload_name"]]["All Variables"].add(var_name)

            for var_name in exp["RAMBLE_VARIABLES"]:
                if is_key_to_skip(var_name):
                    continue
                app_dict[exp["workload_name"]]["All Variables"].add(var_name)
            app_dict[exp["workload_name"]]["All Variables"].add("context")

        if "experiment_template_name" in exp["RAMBLE_RAW_VARIABLES"]:
            template_patterns[exp["application_name"]][exp["workload_name"]].add(
                exp["RAMBLE_RAW_VARIABLES"]["experiment_template_name"]
            )

        for context in exp["CONTEXTS"]:
            if not context["foms"]:
                continue
            app_dict[exp["workload_name"]]["Contexts"].add(context["name"])
            for fom in context["foms"]:
                if fom["origin"] == exp["application_name"]:
                    # If it's a repeat summary, add summary FOMs and stat names
                    if fom["name"] == SummaryFoms.SUMMARY.value:
                        summary_shortname = fom["origin_type"].split("::")[1]
                        if SummaryFoms.SUMMARY.value not in app_dict[exp["workload_name"]]:
                            app_dict[exp["workload_name"]][SummaryFoms.SUMMARY.value] = set()
                        app_dict[exp["workload_name"]][SummaryFoms.SUMMARY.value].add(
                            summary_shortname
                        )
                    else:
                        if fom["origin_type"].startswith("summary::"):
                            summary_shortname = fom["origin_type"].split("::")[1]
                            if "FOM Summary Statistics" not in app_dict[exp["workload_name"]]:
                                app_dict[exp["workload_name"]]["FOM Summary Statistics"] = set()
                            app_dict[exp["workload_name"]]["FOM Summary Statistics"].add(
                                summary_shortname
                            )

                        app_dict[exp["workload_name"]]["FOMs"].add(fom["name"])
                else:
                    # All other objects
                    if fom["origin_type"] in OBJECT_NAMES:
                        obj_dict = result_index[OBJECT_NAMES[fom["origin_type"]]]
                        if fom["origin"] not in obj_dict:
                            obj_dict[fom["origin"]] = {"FOMs": set()}
                        obj_dict[fom["origin"]]["FOMs"].add(fom["name"])

    # Extract template variables used to parameterize experiments
    capture_group = r"(\w+)"
    expansion_pattern = re.compile(rf"{ramble.expander.Expander.expansion_str(capture_group)}")

    for app, wl_and_patterns in template_patterns.items():
        for workload, patterns in wl_and_patterns.items():
            expansion_strs = set()
            if not patterns:
                continue
            for pattern in patterns:
                expansion_strs.update(expansion_pattern.findall(pattern))
            result_index["applications"][app][workload]["Template Variables"] = expansion_strs

    return result_index


def get_all_foms(result_index):
    all_foms = set()
    for obj_type, obj_type_dict in result_index.items():
        if obj_type == "applications":
            for app_dict in obj_type_dict.values():
                for wl_dict in app_dict.values():
                    all_foms.update(wl_dict["FOMs"])
                    if SummaryFoms.SUMMARY.value in wl_dict:
                        all_foms.update(wl_dict[SummaryFoms.SUMMARY.value])
        else:
            for obj_dict in obj_type_dict.values():
                all_foms.update(obj_dict["FOMs"])

    return all_foms


def get_all_vars(result_index):
    all_vars = set()
    for app_dict in result_index["applications"].values():
        for wl_dict in app_dict.values():
            all_vars.update(wl_dict["All Variables"])

    return all_vars


def extract_data(experiments: List[dict], foms: List[str], variables: List[str], where_query=None):
    """Extracts data from the experiments dicts and returns it as a Pandas DataFrame.

    Args:
        experiments (list[dict]): List of experiment dictionaries containing results to extract
        foms (list[str]): List of FOMs to extract from experiments
        variables (list[str]): List of variables to extract from experiments
        where_query (str | None): Pandas query to constrain results

    Returns:
        pandas.core.frame.DataFrame: Pandas DataFrame containing extracted data
    """
    pd = import_pandas()
    extracted_data = []
    for exp in experiments:
        for context in exp["CONTEXTS"]:
            for fom in context["foms"]:
                # Create one DataFrame row per FOM per context per experiment
                if fom["name"] in foms:
                    exp_data = {
                        ReportVars.CONTEXT_NAME.value: context["name"],
                    }

                    for name, report_var in _EXP_BASIC_VARS_MAPPING.items():
                        if name in exp:
                            exp_data[report_var] = exp[name]

                    for name, val in fom.items():
                        if name in _FOM_DICT_MAPPING:
                            exp_data[_FOM_DICT_MAPPING[name]] = val
                        elif name == "fom_type":
                            exp_data["fom_type"] = FomType.from_str(fom["fom_type"]["name"])
                            exp_data[ReportVars.BETTER_DIRECTION.value] = BetterDirection.from_str(
                                fom["fom_type"][ReportVars.BETTER_DIRECTION.value]
                            )

                    # older data exports may not have fom_type stored
                    if "fom_type" not in exp_data:
                        exp_data["fom_type"] = FomType.UNDEFINED
                        exp_data[ReportVars.BETTER_DIRECTION.value] = BetterDirection.INDETERMINATE

                    if variables:
                        for var in variables:
                            if var in exp:
                                exp_data[var] = exp[var]
                            elif var in exp["RAMBLE_VARIABLES"]:
                                exp_data[var] = exp["RAMBLE_VARIABLES"][var]
                            elif var in _ADDITIONAL_VARS:
                                continue
                            else:
                                logger.debug(f"{var} not found in the results data. Skipping.")

                    extracted_data.append(exp_data)

    pd = import_pandas()
    extracted_df = pd.DataFrame.from_dict(extracted_data)

    # Apply where to down select
    if where_query:
        logger.info(f"Applying where query: {where_query}")
        extracted_df = extracted_df.query(where_query)

    return extracted_df


class PlotFactory:
    def determine_plot_type(self, args):
        plot_types = [
            (args.strong_scaling, StrongScalingPlot),
            (args.weak_scaling, WeakScalingPlot),
            (args.compare, ComparisonPlot),
            (args.foms, FomPlot),
            (args.multi_line, MultiLinePlot),
        ]
        for plot_type, plot_class in plot_types:
            if plot_type:
                return (plot_type, plot_class)

    def create_plot_generator(self, args, report_dir_path, exp_results):
        normalize = args.normalize
        logx = args.logx
        logy = args.logy
        split_by = args.split_by
        simplify_names = getattr(args, "simplify_names", False)
        where = getattr(args, "where", None)

        spec, plot_class = self.determine_plot_type(args)

        if spec:
            plot = plot_class(
                spec,
                normalize,
                report_dir_path,
                exp_results,
                logx,
                logy,
                split_by,
                simplify_names=simplify_names,
                where=where,
            )
            return plot

        logger.die("No plots requested. Please specify required plots or see help (-h)")


class PlotGenerator:
    def __init__(
        self,
        spec,
        normalize,
        report_dir_path,
        exp_results,
        logx,
        logy,
        split_by,
        simplify_names=False,
        where=None,
    ):
        pd = import_pandas()
        self.normalize = normalize
        self.spec = spec
        self.report_dir_path = report_dir_path
        self.inventory = {"files": []}
        self.figsize = [12, 8]

        self.exp_results = exp_results
        self.result_index = generate_result_index(exp_results, all_vars=True)
        self.output_df = pd.DataFrame()

        self.logx = logx
        self.logy = logy

        self.split_by = split_by
        self.simplify_names = simplify_names
        self.where = where

        self.have_statistics = False
        self.better_direction = BetterDirection.INDETERMINATE

    def normalize_data(
        self,
        data,
        scale_to_index=False,
        to_col=ReportVars.NORMALIZED_FOM_VALUE.value,
        from_col=ReportVars.FOM_VALUE.value,
    ):
        if data[from_col].iloc[0] == 0:
            raise ArithmeticError(
                "Unable to normalize data. The first value in the series cannot be zero."
            )
        else:
            # Adjusts first y-value to first scale var when >1 (e.g., speedup for 2+ nodes = 2)
            if scale_to_index:
                # Performs inplace edit on data, no need to return
                data.loc[:, to_col] = (
                    data.loc[:, from_col] / data[from_col].iloc[0]
                ) * data.index[0]
            else:
                data.loc[:, to_col] = data.loc[:, from_col] / data[from_col].iloc[0]

    def add_minmax_data(self, selected_data, min_data, max_data, scale_var):
        """When using summary statistics from repeats, adds columns fom_value_min and fom_value_max
        to the selected data.
        """
        min_data[scale_var] = to_numeric_if_possible(min_data[scale_var])
        min_data = min_data.set_index(scale_var)
        max_data[scale_var] = to_numeric_if_possible(max_data[scale_var])
        max_data = max_data.set_index(scale_var)

        selected_data[ReportVars.FOM_VALUE_MIN.value] = to_numeric_if_possible(
            min_data[ReportVars.FOM_VALUE.value]
        )
        selected_data[ReportVars.FOM_VALUE_MAX.value] = to_numeric_if_possible(
            max_data[ReportVars.FOM_VALUE.value]
        )

        if self.normalize:
            self.normalize_data(
                selected_data,
                scale_to_index=True,
                to_col=ReportVars.FOM_VALUE_MIN.value,
                from_col=ReportVars.FOM_VALUE_MIN.value,
            )
            self.normalize_data(
                selected_data,
                scale_to_index=True,
                to_col=ReportVars.FOM_VALUE_MAX.value,
                from_col=ReportVars.FOM_VALUE_MAX.value,
            )

    def get_inventory_path(self):
        return os.path.join(self.report_dir_path, INVENTORY_FILENAME)

    def add_to_inventory(self, filename):
        """Adds a filename to the inventory.

        Args:
            filename: filename to add to inventory.
        """
        self.inventory["files"].append(filename)

    def write_inventory(self):
        with open(self.get_inventory_path(), "w+", encoding="utf-8") as f:
            syaml.dump(self.inventory, stream=f)

    def draw(self, perf_measure, scale_var, series, pdf_report, y_label=None):
        series_data = self.output_df.query(f'series == "{series}"').copy()

        title = (
            f"{perf_measure} vs {scale_var} for {series}"
            f"{get_direction_suffix(self.better_direction)}"
        )
        logger.debug(f"Generating plot for {title}")

        # TODO: prep_draw method in subclass ScalingPlotGenerator, not this class
        fig, ax = self.prep_draw(perf_measure, scale_var)

        if self.normalize:
            ax.plot(
                series_data.index,
                ReportVars.NORMALIZED_FOM_VALUE.value,
                data=series_data,
                marker="o",
                label=f"{perf_measure} (Normalized)",
            )
        else:
            ax.plot(
                series_data.index,
                ReportVars.FOM_VALUE.value,
                data=series_data,
                marker="o",
                label=f"{perf_measure}",
            )
        _, ymax = ax.get_ylim()

        # TODO: the plot can get very compressed for log weak scaling plots
        if not self.logy:
            plt.ylim(0, ymax * 1.1)

        if self.have_statistics:
            logger.debug("Adding fill lines for min and max")
            ax.fill_between(
                series_data.index,
                ReportVars.FOM_VALUE_MIN.value,
                ReportVars.FOM_VALUE_MAX.value,
                data=series_data,
                alpha=0.2,
            )

        try:
            ax.plot(
                series_data.index,
                ReportVars.IDEAL_PERF_VALUE.value,
                data=series_data,
                label="Ideal Value",
            )
        except ValueError:
            logger.debug("Failed to plot ideal_perf_value. Series not found.")

        plt.legend(loc="upper left")

        ax.set_xticks(series_data.index.unique().tolist())
        ax.set_title(title, wrap=True)
        if not y_label or y_label == perf_measure:
            if getattr(self, "perf_unit", "") and not self.normalize:
                y_label = f"{perf_measure} ({self.perf_unit})"
            elif self.normalize:
                y_label = f"{perf_measure} (Normalized)"
            else:
                y_label = perf_measure
        ax.set_ylabel(y_label)

        if getattr(self, "scale_unit", ""):
            scale_var_label = f"{scale_var} ({self.scale_unit})"
        else:
            scale_var_label = scale_var
        ax.set_xlabel(scale_var_label)

        # Rotate to prevent long x-axis labels overlapping. There's probably a better way
        if series_data.index.astype(str).str.len().max() > 4:
            ax.tick_params(axis="x", labelrotation=45)
        fig.tight_layout()

        chart_filename = f"strong-scaling_{perf_measure}_vs_{scale_var}_{series}.png"
        self.write(fig, chart_filename, pdf_report)

    def draw_filler(self, perf_measure, scale_var, series, exception, pdf_report):
        # FIXME: DRY THIS
        """Draws a filler figure in cases where a chart cannot be drawn due to errors."""
        title = f"{perf_measure} vs {scale_var} for {series}"
        logger.debug(f"Generating filler figure for {title}")

        fig, ax = plt.subplots(figsize=self.figsize)
        fig.text(
            0.5,
            0.5,
            exception,
            horizontalalignment="center",
            verticalalignment="center",
            transform=fig.gca().transAxes,
            fontsize=12,
        )
        ax.set_axis_off()
        ax.set_title(title)

        chart_filename = f"strong-scaling_{perf_measure}_vs_{scale_var}_{series}.png"
        self.write(fig, chart_filename, pdf_report)

    def validate_spec(self, chart_spec, result_index):
        """Validates that the FOMs and variables in the chart spec are in the results data."""
        all_foms = get_all_foms(result_index)
        all_vars = get_all_vars(result_index)

        for var in chart_spec:
            if var not in all_foms and var not in all_vars:
                logger.die(
                    f"{var} was not found in the results data. Use `ramble results index -v` "
                    "to see available FOMs and variables."
                )

    def write(self, fig, filename, pdf_report):
        filename = filename.replace(" ", "-")
        plt.savefig(os.path.join(self.report_dir_path, filename), bbox_inches="tight")
        self.add_to_inventory(filename)
        pdf_report.savefig(fig, bbox_inches="tight")
        plt.close(fig)


class ScalingPlotGenerator(PlotGenerator):
    def generate_plot_data(self, pdf_report):
        """Creates a dataframe for plotting line charts with scaling var or FOM on x axis,
        and performance metric on y axis."""
        pd = import_pandas()
        self.validate_spec(self.spec, self.result_index)

        perf_measure, scale_var, *additional_vars = self.spec

        all_foms = get_all_foms(self.result_index)

        foms = [perf_measure]
        variables = []

        if scale_var in all_foms:
            foms.append(scale_var)
        else:
            variables.append(scale_var)

        for var in additional_vars + [self.split_by]:
            if var not in variables and var not in foms:
                variables.append(var)

        results = extract_data(
            self.exp_results,
            foms,
            variables,
            where_query=self.where,
        )

        if results.empty:
            logger.warn(f"No results found matching spec {self.spec}")
            return

        self.perf_unit = ""
        self.scale_unit = ""

        if ReportVars.FOM_UNITS.value in results.columns:
            perf_rows = results[results[ReportVars.FOM_NAME.value] == perf_measure]
            if not perf_rows.empty and pd.notna(perf_rows[ReportVars.FOM_UNITS.value].iloc[0]):
                unit_val = str(perf_rows[ReportVars.FOM_UNITS.value].iloc[0]).strip()
                if unit_val:
                    self.perf_unit = unit_val

            if scale_var in all_foms:
                scale_rows = results[results[ReportVars.FOM_NAME.value] == scale_var]
                if not scale_rows.empty and pd.notna(
                    scale_rows[ReportVars.FOM_UNITS.value].iloc[0]
                ):
                    unit_val = str(scale_rows[ReportVars.FOM_UNITS.value].iloc[0]).strip()
                    if unit_val:
                        self.scale_unit = unit_val

        if scale_var in all_foms:
            if ReportVars.FOM_ORIGIN_TYPE.value in results.columns:
                results["_merge_origin_type"] = results[ReportVars.FOM_ORIGIN_TYPE.value].apply(
                    lambda x: x if isinstance(x, str) and x.startswith("summary::") else "raw"
                )
                origin_key = "_merge_origin_type"
            else:
                origin_key = ReportVars.FOM_ORIGIN_TYPE.value

            merge_keys = [
                k
                for k in [
                    ReportVars.EXP_NAME.value,
                    ReportVars.CONTEXT_NAME.value,
                    origin_key,
                ]
                if k in results.columns
            ]
            scale_df = (
                results[results[ReportVars.FOM_NAME.value] == scale_var][
                    merge_keys + [ReportVars.FOM_VALUE.value]
                ]
                .rename(columns={ReportVars.FOM_VALUE.value: scale_var})
                .drop_duplicates(subset=merge_keys)
            )
            results = results[results[ReportVars.FOM_NAME.value] == perf_measure].copy()
            results = results.merge(scale_df, on=merge_keys, how="inner")
            if "_merge_origin_type" in results.columns:
                results.drop(columns=["_merge_origin_type"], inplace=True)

        if results.empty:
            logger.warn(f"No results found matching spec {self.spec}")
            return

        # Determine which direction is 'better', or 'INDETERMINATE' if missing or ambiguous data
        if len(results.loc[:, ReportVars.BETTER_DIRECTION.value].unique()) == 1:
            self.better_direction = results.loc[:, ReportVars.BETTER_DIRECTION.value].unique()[0]

        # TODO: this needs to support a list for split_by
        # TODO: this currently gets overwritten by series, below
        results.loc[:, ReportVars.SERIES.value] = results.loc[:, self.split_by]

        if additional_vars:
            # TODO: this would be nicer as a group by
            results.loc[:, ReportVars.SERIES.value] = (
                results.loc[:, ReportVars.SERIES.value]
                + "_x_"
                + results[additional_vars].agg("_x_".join, axis=1)
            )

        for series in results.loc[:, ReportVars.SERIES.value].unique():

            # TODO: this needs to account for repeats in a more elegant way
            series_results = results.query(
                f'series == "{series}" and (fom_origin_type == "application" '
                'or fom_origin_type == "modifier" or fom_origin_type == "summary::mean")'
            ).copy()

            series_results[ReportVars.FOM_VALUE.value] = to_numeric_if_possible(
                series_results[ReportVars.FOM_VALUE.value]
            )
            series_results[scale_var] = to_numeric_if_possible(series_results[scale_var])
            series_results = series_results.set_index(scale_var)

            self.validate_data(series_results)

            if self.normalize:
                try:
                    self.normalize_data(series_results, scale_to_index=True)
                except ArithmeticError as e:
                    logger.warn(e)
                    self.draw_filler(perf_measure, scale_var, series, e, pdf_report)
                    continue

            if series_results.loc[:, ReportVars.FOM_ORIGIN_TYPE.value].iloc[0] == "summary::mean":
                self.have_statistics = True

            if self.have_statistics:
                series_min = results.query(
                    f'series == "{series}" and fom_origin_type == "summary::min"'
                ).copy()
                series_max = results.query(
                    f'series == "{series}" and fom_origin_type == "summary::max"'
                ).copy()
                self.add_minmax_data(series_results, series_min, series_max, scale_var)

            series_results = self.add_idealized_data(results, series_results)
            self.output_df = pd.concat([self.output_df, series_results])

            self.draw(perf_measure, scale_var, series, pdf_report)

    def add_idealized_data(self, raw_results, selected_data):
        # Skip if no better direction, but override in subclasses when there's a default_better
        if (
            self.better_direction == BetterDirection.INDETERMINATE
            or self.better_direction == BetterDirection.INAPPLICABLE
        ):
            return selected_data

        if self.normalize:
            first_perf_value = selected_data[ReportVars.NORMALIZED_FOM_VALUE.value].iloc[0]
        else:
            first_perf_value = selected_data[ReportVars.FOM_VALUE.value].iloc[0]

        if first_perf_value == 0:
            logger.warn(
                "Unable to calculate idealized data. The first value in the series cannot be zero."
            )
            return selected_data

        logger.debug(f"Normalizing data (by {first_perf_value})")

        selected_data.loc[:, ReportVars.IDEAL_PERF_VALUE.value] = first_perf_value

        if self.better_direction == BetterDirection.LOWER:
            selected_data[ReportVars.IDEAL_PERF_VALUE.value] = selected_data.loc[
                :, ReportVars.IDEAL_PERF_VALUE.value
            ] / (
                selected_data.index / selected_data.index[0]  # set baseline scaling var to 1
            )
        elif self.better_direction == BetterDirection.HIGHER:
            selected_data[ReportVars.IDEAL_PERF_VALUE.value] = selected_data.loc[
                :, ReportVars.IDEAL_PERF_VALUE.value
            ] * (selected_data.index / selected_data.index[0])

        return selected_data

    def validate_spec(self, chart_spec, result_index):
        if len(chart_spec) < 2:
            logger.die(
                "Scaling plot requires two arguments: " "performance metric and scaling metric"
            )
        super().validate_spec(chart_spec, result_index)

    def validate_data(self, data):
        has_duplicate_index = any(data.index.duplicated())
        if has_duplicate_index:
            logger.debug(data)
            logger.die("Attempting to plot non-unique data. Please reduce data and try again")

    def default_better(self):
        return BetterDirection.INDETERMINATE

    def prep_draw(self, perf_measure, scale_var):
        fig, ax = plt.subplots(figsize=self.figsize)

        if self.logx or self.logy:
            from matplotlib.ticker import ScalarFormatter

            formatter = ScalarFormatter()
            formatter.set_scientific(False)

        if self.logx:
            ax.set_xscale("log", base=2)
            ax.xaxis.set_major_formatter(formatter)

        if self.logy:
            ax.set_yscale("log", base=2)
            ax.yaxis.set_major_formatter(formatter)

        return fig, ax


class WeakScalingPlot(ScalingPlotGenerator):
    plot_type = "weak_scaling"

    def draw(self, perf_measure, scale_var, series, pdf_report):
        y_label = perf_measure

        super().draw(perf_measure, scale_var, series, pdf_report, y_label)

    def add_idealized_data(self, raw_results, selected_data):
        selected_data = super().add_idealized_data(raw_results, selected_data)

        if ReportVars.IDEAL_PERF_VALUE.value in selected_data.columns:
            selected_data.loc[:, ReportVars.IDEAL_PERF_VALUE.value] = selected_data[
                ReportVars.IDEAL_PERF_VALUE.value
            ].iloc[0]
        return selected_data


class StrongScalingPlot(ScalingPlotGenerator):
    plot_type = "strong_scaling"

    def default_better(self):
        if self.normalize:
            return BetterDirection.HIGHER
        else:
            return BetterDirection.LOWER

    def add_idealized_data(self, raw_results, selected_data):
        if self.better_direction is BetterDirection.INDETERMINATE:
            self.better_direction = self.default_better()

        return super().add_idealized_data(raw_results, selected_data)

    def normalize_data(
        self,
        data,
        scale_to_index=True,
        to_col=ReportVars.NORMALIZED_FOM_VALUE.value,
        from_col=ReportVars.FOM_VALUE.value,
    ):
        super().normalize_data(data, scale_to_index, to_col=to_col, from_col=from_col)

    def draw(self, perf_measure, scale_var, series, pdf_report):
        y_label = perf_measure

        super().draw(perf_measure, scale_var, series, pdf_report, y_label)


class FomPlot(PlotGenerator):
    plot_type = "foms"

    def generate_plot_data(self, pdf_report):
        fom_list = get_all_foms(self.result_index)
        results = extract_data(self.exp_results, fom_list, [], where_query=self.where)

        all_foms = results.loc[:, ReportVars.FOM_NAME.value].unique()
        for fom in all_foms:
            series_results = results.query(
                f'fom_name == "{fom}" and (fom_origin_type == "application" or '
                'fom_origin_type == "modifier" or fom_origin_type == "summary::mean" or '
                f'fom_origin_type == "summary::{SummaryFoms.N_TOTAL.value}")'
            ).copy()

            scale_var = "experiment_namespace"

            series_results[ReportVars.FOM_VALUE.value] = to_numeric_if_possible(
                series_results[ReportVars.FOM_VALUE.value]
            )

            series_results[scale_var] = to_numeric_if_possible(series_results[scale_var])

            series_results = series_results.set_index(scale_var)

            if self.normalize:
                self.normalize_data(series_results, scale_to_index=True)

            if series_results.loc[:, ReportVars.FOM_ORIGIN_TYPE.value].iloc[0] == "summary::mean":
                self.have_statistics = True

            if self.have_statistics:
                series_min = results.query(
                    f'fom_name == "{fom}" and fom_origin_type == "summary::min"'
                ).copy()
                series_max = results.query(
                    f'fom_name == "{fom}" and fom_origin_type == "summary::max"'
                ).copy()
                self.add_minmax_data(series_results, series_min, series_max, scale_var)

            if self.simplify_names:
                series_results, stripped_prefix = simplify_experiment_names(series_results)
                self.stripped_prefix = stripped_prefix

            self.output_df = series_results

            unit = series_results.loc[:, ReportVars.FOM_UNITS.value].iloc[0]

            perf_measure = fom
            series = "experiment_name"
            self.draw(perf_measure, scale_var, series, unit, pdf_report)

    # TODO: dry bar plot drawing
    def draw(self, perf_measure, scale_var, series, unit, pdf_report):
        pd = import_pandas()

        self.output_df[ReportVars.FOM_VALUE.value] = to_numeric_if_possible(
            self.output_df[ReportVars.FOM_VALUE.value]
        )

        if not pd.api.types.is_numeric_dtype(self.output_df[ReportVars.FOM_VALUE.value]):
            logger.warn(f"Skipping drawing of non numeric FOM: {perf_measure}")
            return

        # TODO: this should leverage the available min/max to add candle sticks
        ax = self.output_df.plot(y=ReportVars.FOM_VALUE.value, kind="bar", figsize=self.figsize)
        fig = ax.get_figure()

        # ax.set_label('Label via method')
        legend_text = perf_measure
        if unit:
            legend_text = f"{perf_measure} ({unit})"

        ax.legend([legend_text])

        # If all FOMs are either higher or lower is better, add it to chart title
        ax.set_title(f"{perf_measure} by experiment", wrap=True)

        if self.simplify_names and getattr(self, "stripped_prefix", None):
            ax.set_xlabel(f"experiment (prefix '{self.stripped_prefix}' stripped)")
        else:
            ax.set_xlabel("experiment")

        # FIXME: Rotate to prevent long x-axis labels overlapping. This can make the chart
        # very small but experiment names are readable (for smaller number of experiments)
        if self.output_df.index.astype(str).str.len().max() > 4:
            ax.tick_params(axis="x", labelrotation=90)
            fig.tight_layout()

        chart_filename = f"foms_{perf_measure}_by_experiments.png"
        self.write(fig, chart_filename, pdf_report)


class ComparisonPlot(PlotGenerator):
    plot_type = "comparison"

    def draw(self, perf_measure, scale_var, series, pdf_report):
        ax = self.output_df.plot(kind="bar", figsize=self.figsize)
        fig = ax.get_figure()

        # If all FOMs are either higher or lower is better, add it to chart title
        title_suffix = ""
        ax.set_title(
            f'{" vs ".join(perf_measure)} by {" and ".join(series)} {title_suffix}', wrap=True
        )

        if self.simplify_names and getattr(self, "stripped_prefix", None):
            ax.set_xlabel(f'{" and ".join(series)} (prefix \'{self.stripped_prefix}\' stripped)')

        # FIXME: this has a hard time fitting well on screen
        fig.tight_layout()

        chart_filename = f'{"_vs_".join(perf_measure)}_by_{"_and_".join(series)}.png'
        self.write(fig, chart_filename, pdf_report)

    def generate_plot_data(self, pdf_report):
        # Break out input args into FOMs and dimensions
        foms = []
        dimensions = []

        all_foms = get_all_foms(self.result_index)

        for input_spec in self.spec:
            if input_spec in all_foms:
                foms.append(input_spec)
            else:
                dimensions.append(input_spec)

        if not dimensions:
            dimensions.append("experiment_name")

        raw_results = extract_data(self.exp_results, foms, dimensions, where_query=self.where)

        if self.simplify_names:
            for col in ["experiment_name", "experiment_namespace"]:
                if col in raw_results.columns:
                    raw_results, stripped_prefix = simplify_experiment_names(
                        raw_results, index_col=col
                    )
                    if stripped_prefix:
                        self.stripped_prefix = stripped_prefix

        logger.debug(raw_results)
        raw_results.loc[:, "Figure of Merit"] = (
            raw_results.loc[:, ReportVars.FOM_NAME.value]
            + " ("
            + raw_results.loc[:, ReportVars.FOM_UNITS.value]
            + ")"
        )

        raw_results[ReportVars.FOM_VALUE.value] = to_numeric_if_possible(
            raw_results[ReportVars.FOM_VALUE.value]
        )

        plot_col = ReportVars.FOM_VALUE.value
        if self.normalize:
            self.normalize_data(raw_results)
            plot_col = ReportVars.NORMALIZED_FOM_VALUE.value

        # TODO: remove pivot?
        compare_pivot = raw_results.pivot_table(
            plot_col, index=dimensions, columns="Figure of Merit"
        )
        self.output_df = compare_pivot

        # Pivot table aggregates values by mean. Check if results were aggregated and label them
        # Raw results have FOMs by row, pivot by columns, so multiply the pivot rows x cols
        # print(f'raw values = {len(raw_results)}  vs pivot values = {len(compare_pivot)} x
        # {len(compare_pivot.columns)} ={len(compare_pivot) * len(compare_pivot.columns)}')

        perf_measure = foms
        scale_var = ""
        series = dimensions
        self.draw(perf_measure, scale_var, series, pdf_report)


class MultiLinePlot(ScalingPlotGenerator):
    plot_type = "multi_line"
    series_to_plot: List[str] = []

    def default_better(self):
        return BetterDirection.HIGHER

    def normalize_data(
        self,
        data,
        scale_to_index=True,
        to_col=ReportVars.NORMALIZED_FOM_VALUE.value,
        from_col=ReportVars.FOM_VALUE.value,
    ):
        super().normalize_data(
            data,
            scale_to_index,
            to_col=to_col,
            from_col=from_col,
        )

    def draw_multiline(self, perf_measure, scale_var, pdf_report, y_label):
        # TODO: add suffix 'higher/lower is better' to chart title based on better_direction
        title = f"{perf_measure} vs {scale_var}"
        logger.debug(f"Generating plot for {title}")

        # TODO: prep_draw method in subclass ScalingPlotGenerator, not this class
        fig, ax = self.prep_draw(perf_measure, scale_var)

        for series in self.output_df.loc[:, ReportVars.SERIES.value].unique():
            series_data = self.output_df.query(f'series == "{series}"').copy()
            if self.normalize:
                ax.plot(
                    series_data.index,
                    ReportVars.NORMALIZED_FOM_VALUE.value,
                    data=series_data,
                    marker="o",
                    label=f"{series} (Normalized)",
                )
            else:
                ax.plot(
                    series_data.index,
                    ReportVars.FOM_VALUE.value,
                    data=series_data,
                    marker="o",
                    label=f"{series}",
                )

            if self.have_statistics:
                logger.debug("Adding fill lines for min and max")
                ax.fill_between(
                    series_data.index,
                    ReportVars.FOM_VALUE_MIN.value,
                    ReportVars.FOM_VALUE_MAX.value,
                    data=series_data,
                    alpha=0.2,
                )

        _, ymax = ax.get_ylim()

        # TODO: the plot can get very compressed for log weak scaling plots
        if not self.logy:
            plt.ylim(0, ymax * 1.1)

        plt.legend(loc="upper left")

        ax.set_xticks(self.output_df.index.unique().tolist())
        ax.set_title(title, wrap=True)
        if getattr(self, "perf_unit", "") and not self.normalize:
            y_label = f"{perf_measure} ({self.perf_unit})"
        elif self.normalize:
            y_label = f"{perf_measure} (Normalized)"
        ax.set_ylabel(y_label)

        if getattr(self, "scale_unit", ""):
            scale_var_label = f"{scale_var} ({self.scale_unit})"
        else:
            scale_var_label = scale_var
        ax.set_xlabel(scale_var_label)

        # This is to prevent x-axis labels overlapping but there's probably a better way
        if self.output_df.index.astype(str).str.len().max() > 4:
            ax.tick_params(axis="x", labelrotation=45)
        fig.tight_layout()

        chart_filename = f"multi_line_{perf_measure}_vs_{scale_var}_all-series.png"
        self.write(fig, chart_filename, pdf_report)

    def generate_plot_data(self, pdf_report):
        super().generate_plot_data(pdf_report)

        if getattr(self, "output_df", None) is None or self.output_df.empty:
            return

        perf_measure, scale_var, *_ = self.spec
        y_label = perf_measure

        self.draw_multiline(perf_measure, scale_var, pdf_report, y_label)


def get_reports_path():
    """Returns current directory of ramble-created reports"""
    path_in_config = ramble.config.get("config:report_dirs")
    if not path_in_config:
        logger.die(
            "No config:report_dirs setting found in configuration. To add one,  "
            'use command: ramble config add "config:report_dirs:~/.ramble/reports"'
        )

    report_path = ramble.util.path.canonicalize_path(str(path_in_config))
    return report_path


def make_report(experiments: list, ws_name, args):
    dt = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    report_dir_root = get_reports_path()

    report_base = f"{ws_name}"
    report_name = f"{report_base}.{dt}"
    report_dir_path = os.path.join(report_dir_root, report_name)
    fs.mkdirp(report_dir_path)

    plot_factory = PlotFactory()
    plot = plot_factory.create_plot_generator(args, report_dir_path, experiments)
    plot_type = plot.plot_type

    pdf_filename = f"{report_name}.{plot_type}.pdf"
    pdf_path = os.path.join(report_dir_path, pdf_filename)
    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)
        plot.add_to_inventory(pdf_filename)

    if os.path.isfile(pdf_path):
        plot.write_inventory()
        symlinks_created = []

        for base in report_base, "reports":
            # Symlink specific workspace latest file
            latest_file = f"{base}.latest.pdf"
            latest_path = os.path.join(report_dir_root, latest_file)
            symlinks_created.append(latest_path)
            create_symlink(pdf_path, latest_path)

            latest_file = f"{base}.{plot_type}.latest.pdf"
            latest_path = os.path.join(report_dir_root, latest_file)
            symlinks_created.append(latest_path)
            create_symlink(pdf_path, latest_path)

        logger.all_msg("Report generated successfully. A PDF summary is available at:")
        logger.all_msg(f"  {pdf_path}")
        logger.all_msg("Individual chart images are available at:")
        logger.all_msg(f"  {report_dir_path}")
        logger.all_msg("Symlinks updated:")
        for path in symlinks_created:
            logger.all_msg(f"  {path}")
