# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

# Test command line args

# Test file import for JSON (done) and YAML
# - non-repeated experiments
# - repeated experiments

# Test normalization of data, and error when first value is zero

# Test that PDF is generated and contains data (size > some value?)

import copy
import os
import re
from typing import Any, Dict, Optional

import pandas as pd

# Possible to test that a specific chart was correctly generated? Not sure...
import pytest
from matplotlib.backends.backend_pdf import PdfPages

import ramble.reports
from ramble.main import RambleCommand
from ramble.util import foms, json_util

import spack.util.spack_yaml as syaml

config = RambleCommand("config")
results = RambleCommand("results")


def create_test_fom_result(
    name,
    value,
    units,
    origin,
    origin_type,
    fom_type=None,
):
    fom_dict = {
        "name": name,
        "value": value,
        "units": units,
        "origin": origin,
        "origin_type": origin_type,
    }
    if fom_type is not None:
        fom_dict["fom_type"] = foms.FomType.to_dict(fom_type)
    return fom_dict


def create_test_exp_result(
    ramble_status: str,
    experiment_name: str,
    application_name: str,
    workload_name: str,
    foms: list,
    ramble_vars: Optional[dict],
    ramble_raw_vars: Optional[dict],
    **kwargs,
):
    """Creates an experiment results dict in the format of results imported from JSON or YAML.

    args:
        ramble_status: Status (e.g. "SUCCESS", "FAILED")
        experiment_name: name of the experiment
        application_name: name of the app
        workload_name: name of the workload
        foms: List of tuples (context, (fom_name, value, units, origin, origin_type, fom_type))
        ramble_vars: Dict of any variables to add to RAMBLE_VARIABLES
        ramble_raw_vars: Dict of any variables to add to RAMBLE_RAW_VARIABLES
        kwargs: Any kwargs will be added to the experiment dict as k/v pairs, (e.g., "n_nodes=1")
    """
    test_exp_dict: Dict[str, Any] = {
        "RAMBLE_STATUS": ramble_status,
        "experiment_name": experiment_name,
        "experiment_namespace": f"{application_name}.{workload_name}.{experiment_name}",
        "application_name": application_name,
        "workload_name": workload_name,
        "workload_namespace": f"{application_name}.{workload_name}",
        "context_name": "null",
        "RAMBLE_VARIABLES": {},
        "RAMBLE_RAW_VARIABLES": {},
        "CONTEXTS": [],
    }

    test_exp_dict["name"] = test_exp_dict["experiment_namespace"]

    if ramble_vars:
        test_exp_dict["RAMBLE_VARIABLES"] = ramble_vars
    if ramble_raw_vars:
        test_exp_dict["RAMBLE_RAW_VARIABLES"] = ramble_raw_vars

    foms_list: Dict[str, list] = {
        "null": [],
    }

    if not foms:
        foms = []

    for context, fom in foms:
        if context not in foms_list:
            foms_list[context] = []
        foms_list[context].append(create_test_fom_result(*fom))

    for context, foms in foms_list.items():
        test_exp_dict["CONTEXTS"].append(
            {
                "name": context,
                "display_name": context,
                "foms": foms,
            }
        )

    if kwargs:
        test_exp_dict.update(kwargs)

    return test_exp_dict


app_name = "test_app"
wl_name = "test_workload"

single_experiments = [
    create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="single_exp_1",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            ("null", ("fom_1", 42.0, "", app_name, "application", foms.FomType.MEASURE)),
            ("null", ("fom_2", 50, "", app_name, "application", foms.FomType.MEASURE)),
        ],
        ramble_vars={"repeat_index": "0"},
        ramble_raw_vars={},
        n_nodes=1,
    ),
    create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="single_exp_2",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            ("null", ("fom_1", 28.0, "", app_name, "application", foms.FomType.MEASURE)),
            ("null", ("fom_2", 55, "", app_name, "application", foms.FomType.MEASURE)),
        ],
        ramble_vars={"repeat_index": "0"},
        ramble_raw_vars={},
        n_nodes=2,
    ),
]

repeat_experiments = [
    create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="repeat_exp_1",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            (
                "null",
                (
                    foms.SummaryFoms.SUMMARY.value,
                    2,
                    "repeats",
                    app_name,
                    f"summary::{foms.SummaryFoms.N_TOTAL.value}",
                    foms.FomType.MEASURE,
                ),
            ),
            (
                "null",
                (
                    foms.SummaryFoms.SUMMARY.value,
                    2,
                    "repeats",
                    app_name,
                    f"summary::{foms.SummaryFoms.N_SUCCESS.value}",
                    foms.FomType.MEASURE,
                ),
            ),
            ("null", ("fom_1", 28.0, "s", app_name, "summary::min", foms.FomType.TIME)),
            ("null", ("fom_1", 30.0, "s", app_name, "summary::max", foms.FomType.TIME)),
            ("null", ("fom_1", 29.0, "s", app_name, "summary::mean", foms.FomType.TIME)),
        ],
        ramble_vars={"repeat_index": "0"},
        ramble_raw_vars={},
        n_nodes=2,
        N_REPEATS=2,
    ),
    create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="repeat_exp_1.1",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            ("null", ("fom_1", 28.0, "s", app_name, "application", foms.FomType.TIME)),
            ("null", ("fom_2", 55, "", app_name, "application", foms.FomType.MEASURE)),
        ],
        ramble_vars={"repeat_index": "1"},
        ramble_raw_vars={},
        n_nodes=2,
        N_REPEATS=0,
        experiment_namespace=f"{app_name}.{wl_name}.repeat_exp_1",
    ),
    create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="repeat_exp_1.2",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            ("null", ("fom_1", 30.0, "s", app_name, "application", foms.FomType.TIME)),
            ("null", ("fom_2", 55, "", app_name, "application", foms.FomType.MEASURE)),
        ],
        ramble_vars={"repeat_index": "2"},
        ramble_raw_vars={},
        n_nodes=2,
        N_REPEATS=0,
        experiment_namespace=f"{app_name}.{wl_name}.repeat_exp_1",
    ),
]

all_experiments = repeat_experiments + single_experiments


@pytest.mark.parametrize(
    "values",
    [
        (ramble.reports.StrongScalingPlot, "fom_1", 42.0, 42.0, 42.0, 28.0, 28.0, 21.0, False),
        (ramble.reports.StrongScalingPlot, "fom_1", 42.0, 1.0, 1.0, 28.0, 28.0 / 42.0, 2.0, True),
        (ramble.reports.WeakScalingPlot, "fom_2", 50, 50, None, 55, 55, None, False),
        (ramble.reports.WeakScalingPlot, "fom_2", 50, 1.0, None, 55, 1.1, None, True),
    ],
)
def test_scaling_plots(mutable_mock_workspace_path, tmpdir_factory, values):
    report_name = "unit_test"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    plot_type, fom_name, fv1, nfv1, ideal1, fv2, nfv2, ideal2, normalize = values

    test_spec = [fom_name, "n_nodes"]

    # Create a dataframe that matches the expected output of extract_data()
    ideal_data = [
        {
            "experiment_name": "single_exp_1",
            "experiment_namespace": f"{app_name}.{wl_name}.single_exp_1",
            "application_name": app_name,
            "workload_name": wl_name,
            "workload_namespace": f"{app_name}.{wl_name}",
            "context_name": "null",
            "fom_name": fom_name,
            "fom_type": foms.FomType.MEASURE,
            "better_direction": foms.BetterDirection.INDETERMINATE,
            "fom_value": fv1,
            "fom_units": "",
            "fom_origin": app_name,
            "fom_origin_type": "application",
            "series": f"{app_name}.{wl_name}",
            "n_nodes": 1,
        },
        {
            "experiment_name": "single_exp_2",
            "experiment_namespace": f"{app_name}.{wl_name}.single_exp_2",
            "application_name": app_name,
            "workload_name": wl_name,
            "workload_namespace": f"{app_name}.{wl_name}",
            "context_name": "null",
            "fom_name": fom_name,
            "fom_type": foms.FomType.MEASURE,
            "better_direction": foms.BetterDirection.INDETERMINATE,
            "fom_value": fv2,
            "fom_units": "",
            "fom_origin": app_name,
            "fom_origin_type": "application",
            "series": f"{app_name}.{wl_name}",
            "n_nodes": 2,
        },
    ]

    # ideal_perf_value is only calculated when there is a BETTER_DIRECTION
    # If INDETERMINATE, StrongScalingPlot sets default BETTER_DIRECTION & WeakScalingPlot does not
    if fom_name == "fom_1":
        ideal_data[0]["ideal_perf_value"] = ideal1
        ideal_data[1]["ideal_perf_value"] = ideal2

    if normalize:
        ideal_data[0]["normalized_fom_value"] = nfv1
        ideal_data[1]["normalized_fom_value"] = nfv2

    ideal_df = pd.DataFrame(ideal_data, columns=ideal_data[0].keys())

    # Update index to match
    ideal_df = ideal_df.set_index("n_nodes")

    logx = False
    logy = False
    split_by = "workload_namespace"

    plot = plot_type(
        test_spec, normalize, report_dir_path, single_experiments, logx, logy, split_by
    )

    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

        # Sort columns alphabetically, order is not important
        plot.output_df.sort_index(axis=1, inplace=True)
        ideal_df.sort_index(axis=1, inplace=True)

        assert plot.output_df.equals(ideal_df)
        assert os.path.isfile(pdf_path)


def test_repeat_import(mutable_mock_workspace_path):
    where_query = None
    filtered_experiments = ramble.reports.filter_exp_results(all_experiments)
    results_df = ramble.reports.extract_data(filtered_experiments, "fom_1", where_query)

    # DF contains only summary exp and not individual repeats
    assert "repeat_exp_1" in results_df.values
    assert "repeat_exp_1.1" not in results_df.values
    assert "single_exp_1" in results_df.values

    # Summary FOMs are present in DF, types converted to objects
    row_mean = results_df.query("fom_origin_type == 'summary::mean'")
    assert row_mean["fom_value"].values == [29.0]
    assert row_mean["fom_type"].values == [foms.FomType.TIME]
    assert row_mean["better_direction"].values == [foms.BetterDirection.LOWER]

    single_exp_rows = results_df.query("experiment_name == 'single_exp_1' and fom_name == 'fom_1'")
    assert single_exp_rows["fom_value"].values == [42.0]


def test_fom_plot(mutable_mock_workspace_path, tmpdir_factory):
    report_name = "unit_test"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    plot = ramble.reports.FomPlot(
        None, False, report_dir_path, single_experiments, False, False, None
    )
    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

    assert os.path.isfile(pdf_path)
    assert os.path.isfile(os.path.join(report_dir_path, "foms_fom_1_by_experiments.png"))


def test_compare_plot(mutable_mock_workspace_path, tmpdir_factory):
    report_name = "unit_test"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    spec = ["fom_1", "n_nodes"]
    plot = ramble.reports.ComparisonPlot(
        spec, False, report_dir_path, single_experiments, False, False, None
    )
    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

    assert os.path.isfile(pdf_path)
    assert os.path.isfile(os.path.join(report_dir_path, "fom_1_by_n_nodes.png"))


def test_compare_plot_with_simplify_names(mutable_mock_workspace_path, tmpdir_factory):
    report_name = "unit_test_simplify_compare"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    spec = ["fom_1", "experiment_name"]
    plot = ramble.reports.ComparisonPlot(
        spec, False, report_dir_path, single_experiments, False, False, None, simplify_names=True
    )
    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

    assert os.path.isfile(pdf_path)
    assert os.path.isfile(os.path.join(report_dir_path, "fom_1_by_experiment_name.png"))


def test_multiline_plot(mutable_mock_workspace_path, mutable_config, tmpdir_factory):
    results_dir_path = tmpdir_factory.mktemp("unit_test")
    results_file = os.path.join(results_dir_path, "results.json")

    test_exp_results = {"experiments": all_experiments}

    with open(results_file, "w+", encoding="utf-8") as f:
        json_util.dump(test_exp_results, f)

    with ramble.config.override("config:report_dirs", results_dir_path):
        output = results(
            "report",
            "-f",
            results_file,
            "--multi-line",
            "fom_1",
            "n_nodes",
            "--split-by",
            "experiment_name",
        )

    assert "Report generated successfully" in output

    timestamp_capture = re.compile(r"\.(\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2})")
    ts = timestamp_capture.search(output).group(1)
    out_path = os.path.join(results_dir_path, f"unknown_workspace.{ts}")

    assert os.path.isdir(out_path)
    assert os.path.isfile(os.path.join(out_path, f"unknown_workspace.{ts}.multi_line.pdf"))

    inventory_path = os.path.join(out_path, "inventory.yaml")
    assert os.path.isfile(inventory_path)

    with open(inventory_path, encoding="utf-8") as f:
        inventory = syaml.load(f)

    for file in inventory["files"]:
        assert os.path.isfile(os.path.join(out_path, file))


def test_multiline_format_lines_by(
    mutable_mock_workspace_path, mutable_config, tmpdir_factory, monkeypatch
):
    results_dir_path = tmpdir_factory.mktemp("unit_test_fmt")
    results_file = os.path.join(results_dir_path, "results.json")

    test_exps = [
        create_test_exp_result(
            ramble_status="SUCCESS",
            experiment_name=f"exp_{i}",
            application_name="app",
            workload_name="wl",
            foms=[
                ("null", ("fom_1", 10.0 * i, "s", "app", "application", foms.FomType.TIME)),
            ],
            ramble_vars={"repeat_index": "0", "line_style_var": f"style_{i}"},
            ramble_raw_vars={},
            n_nodes=1,
        )
        for i in range(1, 4)
    ]

    test_exp_results = {"experiments": test_exps}

    with open(results_file, "w+", encoding="utf-8") as f:
        json_util.dump(test_exp_results, f)

    captured_linestyles = []
    orig_write = ramble.reports.MultiLinePlot.write

    def spy_write(self, fig, filename, pdf_report):
        if filename.startswith("multi_line"):
            ax = fig.axes[0]
            captured_linestyles.extend([line.get_linestyle() for line in ax.get_lines()])
        return orig_write(self, fig, filename, pdf_report)

    monkeypatch.setattr(ramble.reports.MultiLinePlot, "write", spy_write)

    with ramble.config.override("config:report_dirs", results_dir_path):
        output = results(
            "report",
            "-f",
            results_file,
            "--multi-line",
            "fom_1",
            "n_nodes",
            "--split-by",
            "experiment_name",
            "--format-lines-by",
            "line_style_var",
        )

    assert "Report generated successfully" in output

    timestamp_capture = re.compile(r"\.(\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2})")
    ts = timestamp_capture.search(output).group(1)
    out_path = os.path.join(results_dir_path, f"unknown_workspace.{ts}")

    assert os.path.isdir(out_path)
    assert os.path.isfile(os.path.join(out_path, f"unknown_workspace.{ts}.multi_line.pdf"))

    assert len(set(captured_linestyles)) == 3
    assert set(captured_linestyles) == {"-", "--", "-."}


def test_where_query(mutable_mock_workspace_path):
    where_query = 'fom_name == "fom_1"'
    foms = ["fom_1", "fom_2"]
    results_df = ramble.reports.extract_data(single_experiments, foms, [], where_query)
    filtered_foms = results_df["fom_name"].tolist()

    assert "fom_1" in filtered_foms
    assert "fom_2" not in filtered_foms


def test_extract_data_without_fom_type():
    """Test extract_data with older data exports that do not have fom_type stored."""
    legacy_exp = create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="legacy_exp_1",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            ("null", ("legacy_fom", 100.0, "s", app_name, "application")),
            ("null", ("modern_fom", 50.0, "MB", app_name, "application", foms.FomType.MEASURE)),
        ],
        ramble_vars={"repeat_index": "0"},
        ramble_raw_vars={},
    )

    df_legacy = ramble.reports.extract_data([legacy_exp], ["legacy_fom"], [])
    assert len(df_legacy) == 1
    row_legacy = df_legacy.iloc[0]
    assert row_legacy["fom_name"] == "legacy_fom"
    assert row_legacy["fom_value"] == 100.0
    assert row_legacy["fom_units"] == "s"
    assert row_legacy["fom_type"] == foms.FomType.UNDEFINED
    assert row_legacy["better_direction"] == foms.BetterDirection.INDETERMINATE

    df_both = ramble.reports.extract_data([legacy_exp], ["legacy_fom", "modern_fom"], [])
    assert len(df_both) == 2

    row_legacy_both = df_both[df_both["fom_name"] == "legacy_fom"].iloc[0]
    assert row_legacy_both["fom_type"] == foms.FomType.UNDEFINED
    assert row_legacy_both["better_direction"] == foms.BetterDirection.INDETERMINATE

    row_modern = df_both[df_both["fom_name"] == "modern_fom"].iloc[0]
    assert row_modern["fom_type"] == foms.FomType.MEASURE
    assert row_modern["better_direction"] == foms.BetterDirection.INDETERMINATE


def test_extract_data_variables():
    """Test variable extraction in extract_data across all variable sources."""
    exp = create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="var_exp_1",
        application_name=app_name,
        workload_name=wl_name,
        foms=[
            ("null", ("fom_1", 42.0, "s", app_name, "application", foms.FomType.TIME)),
        ],
        ramble_vars={"var_in_ramble": "ramble_val"},
        ramble_raw_vars={},
        var_in_exp="exp_val",
    )
    # Remove top-level context_name to test _ADDITIONAL_VARS handling
    exp.pop("context_name", None)

    variables = [
        "var_in_exp",
        "var_in_ramble",
        "context_name",
        "non_existent_var",
    ]
    df = ramble.reports.extract_data([exp], ["fom_1"], variables)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["var_in_exp"] == "exp_val"
    assert row["var_in_ramble"] == "ramble_val"
    assert row["context_name"] == "null"
    assert "non_existent_var" not in df.columns


def test_multiple_groupby(mutable_mock_workspace_path, tmpdir_factory, capsys):
    report_name = "unit_test"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    in_data = [
        ("exp_1", 1, "app_v1", "test_wl_1", "1.0"),
        ("exp_2", 1, "app_v1", "test_wl_2", "2.0"),
        ("exp_3", 2, "app_v1", "test_wl_1", "3.0"),
        ("exp_4", 2, "app_v1", "test_wl_2", "4.0"),
        ("exp_5", 1, "app_v2", "test_wl_1", "10.0"),
        ("exp_6", 1, "app_v2", "test_wl_2", "20.0"),
        ("exp_7", 2, "app_v2", "test_wl_1", "30.0"),
        ("exp_8", 2, "app_v2", "test_wl_2", "40.0"),
    ]
    experiments = []
    for exp in in_data:
        name, n_nodes, test_app, test_wl, fom_value = exp

        experiment = create_test_exp_result(
            ramble_status="SUCCESS",
            experiment_name=name,
            application_name=test_app,
            workload_name=test_wl,
            foms=[
                ("null", ("fom_1", fom_value, "", test_app, "application", foms.FomType.MEASURE)),
            ],
            ramble_vars={},
            ramble_raw_vars={},
            n_nodes=n_nodes,
        )
        experiments.append(experiment)

    test_spec = ["fom_1", "n_nodes", "workload_name"]
    logx = False
    logy = False
    split_by = "workload_name"
    plot = ramble.reports.StrongScalingPlot(
        test_spec, False, report_dir_path, experiments, logx, logy, split_by
    )

    with PdfPages(pdf_path) as pdf_report:
        with pytest.raises(SystemExit):
            plot.generate_plot_data(pdf_report)
        captured = capsys.readouterr().err
        assert "Error: Attempting to plot non-unique data." in captured

    test_spec = ["fom_1", "n_nodes", "workload_name", "application_name"]

    plot = ramble.reports.StrongScalingPlot(
        test_spec, False, report_dir_path, experiments, logx, logy, split_by
    )
    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

    assert os.path.isfile(pdf_path)
    assert os.path.isfile(
        os.path.join(
            report_dir_path, "strong-scaling_fom_1_vs_n_nodes_test_wl_1_x_test_wl_1_x_app_v1.png"
        )
    )


def test_scaling_fom_as_scale_var(tmpdir_factory):
    report_name = "unit_test_fom_scale_var"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    in_data = [
        ("exp_1", "100000", "1.0"),
        ("exp_2", "200000", "2.0"),
        ("exp_3", "300000", "3.0"),
    ]
    experiments = []
    for exp in in_data:
        name, fom_scale_val, fom_perf_val = exp

        experiment = create_test_exp_result(
            ramble_status="SUCCESS",
            experiment_name=name,
            application_name="app_v1",
            workload_name="test_wl_1",
            foms=[
                (
                    "null",
                    (
                        "y",
                        fom_perf_val,
                        "GFLOPs",
                        "app_v1",
                        "application",
                        foms.FomType.MEASURE,
                    ),
                ),
                (
                    "null",
                    (
                        "x",
                        fom_scale_val,
                        "MB",
                        "app_v1",
                        "application",
                        foms.FomType.MEASURE,
                    ),
                ),
            ],
            ramble_vars={},
            ramble_raw_vars={},
        )
        experiments.append(experiment)

    test_spec = ["y", "x"]
    logx = False
    logy = False
    split_by = "workload_name"
    plot = ramble.reports.MultiLinePlot(
        test_spec, False, report_dir_path, experiments, logx, logy, split_by
    )

    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

    assert os.path.isfile(pdf_path)
    assert os.path.isfile(os.path.join(report_dir_path, "multi_line_y_vs_x_all-series.png"))

    # Test normalized plot (covers normalize=True y_label)
    plot_norm = ramble.reports.MultiLinePlot(
        test_spec, True, report_dir_path, experiments, logx, logy, split_by
    )
    with PdfPages(pdf_path) as pdf_report:
        plot_norm.generate_plot_data(pdf_report)


def test_scaling_plot_invalid_spec(tmpdir_factory, capsys):
    """Test ScalingPlotGenerator.validate_spec rejects specs with fewer than two arguments."""
    report_name = "unit_test_invalid_spec"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    invalid_spec = ["fom_1"]
    plot_invalid = ramble.reports.StrongScalingPlot(
        invalid_spec,
        False,
        report_dir_path,
        single_experiments,
        False,
        False,
        "workload_namespace",
    )
    with PdfPages(pdf_path) as pdf_report:
        with pytest.raises(SystemExit):
            plot_invalid.generate_plot_data(pdf_report)
        captured = capsys.readouterr().err
        assert "Scaling plot requires two arguments" in captured


def test_scaling_plot_empty_results(tmpdir_factory):
    report_name = "unit_test_empty_results"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    exp_1 = create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="exp_1",
        application_name="app_v1",
        workload_name="test_wl_1",
        foms=[
            (
                "null",
                (
                    "fom_perf",
                    "1.0",
                    "GFLOPs",
                    "app_v1",
                    "application",
                    foms.FomType.MEASURE,
                ),
            ),
            (
                "null",
                (
                    "fom_scale",
                    "100",
                    "MB",
                    "app_v1",
                    "application",
                    foms.FomType.MEASURE,
                ),
            ),
        ],
        ramble_vars={},
        ramble_raw_vars={},
    )
    exp_alt = create_test_exp_result(
        ramble_status="SUCCESS",
        experiment_name="exp_alt",
        application_name="app_v1",
        workload_name="test_wl_1",
        foms=[
            (
                "null",
                (
                    "fom_other",
                    "10",
                    "MB",
                    "app_v1",
                    "application",
                    foms.FomType.MEASURE,
                ),
            ),
        ],
        ramble_vars={},
        ramble_raw_vars={},
    )

    test_spec = ["fom_perf", "fom_scale"]
    logx = False
    logy = False
    split_by = "workload_name"

    # Test empty results when extract_data returns empty via where clause
    plot_empty_where = ramble.reports.MultiLinePlot(
        test_spec,
        False,
        report_dir_path,
        [exp_1],
        logx,
        logy,
        split_by,
        where='experiment_name == "non_existent"',
    )
    with PdfPages(pdf_path) as pdf_report:
        plot_empty_where.generate_plot_data(pdf_report)

    # Test empty results when scale_df merge produces no matching scale FOM
    empty_spec_scale = ["fom_perf", "fom_other"]
    plot_empty_merge = ramble.reports.MultiLinePlot(
        empty_spec_scale, False, report_dir_path, [exp_1, exp_alt], logx, logy, split_by
    )
    with PdfPages(pdf_path) as pdf_report:
        plot_empty_merge.generate_plot_data(pdf_report)


@pytest.mark.parametrize("format", ["json", "yaml"])
def test_index_printing(mutable_mock_workspace_path, tmpdir_factory, format):
    test_exps = copy.deepcopy(all_experiments)

    for exp in test_exps:
        if exp["experiment_name"] == "single_exp_1":
            exp["RAMBLE_RAW_VARIABLES"][
                "experiment_template_name"
            ] = "template_{variable_to_include_single}"
        elif exp["experiment_name"] == "repeat_exp_1":
            exp["RAMBLE_RAW_VARIABLES"][
                "experiment_template_name"
            ] = "template_{variable_to_include_repeat}"
        # Repeat children should be excluded from results
        elif exp["experiment_name"] == "repeat_exp_1.1":
            exp["RAMBLE_RAW_VARIABLES"][
                "experiment_template_name"
            ] = "{repeat_exp_template}_variable_to_exclude"
            exp["CONTEXTS"][0]["foms"].append(
                create_test_fom_result(
                    "repeat_fom_to_exclude", 0, "", app_name, "application", foms.FomType.MEASURE
                )
            )

    # Failed experiments should be excluded from results
    test_exps.append(
        create_test_exp_result(
            ramble_status="FAILED",
            experiment_name="failed_exp_1",
            application_name=app_name,
            workload_name=wl_name,
            foms=[
                (
                    "null",
                    (
                        "single_fom_to_exclude",
                        67,
                        "",
                        app_name,
                        "application",
                        foms.FomType.MEASURE,
                    ),
                ),
            ],
            ramble_vars={"repeat_index": "0"},
            ramble_raw_vars={
                "experiment_template_name": "{single_exp_template}_variable_to_exclude"
            },
            n_nodes=1,
        ),
    )

    test_exp_results = {"experiments": test_exps}

    results_dir_path = tmpdir_factory.mktemp("unit_test")
    results_file = os.path.join(results_dir_path, f"results.{format}")

    with open(results_file, "w+", encoding="utf-8") as f:
        if format == "json":
            json_util.dump(test_exp_results, f)
        elif format == "yaml":
            syaml.dump(test_exp_results, stream=f)

    result_index = results("index", "-f", results_file)

    include = [
        wl_name,
        "fom_1",
        "variable_to_include_single",
        "variable_to_include_repeat",
    ]
    exclude = [
        "single_exp_template",
        "repeat_exp_template",
        "single_fom_to_exclude",
        "repeat_fom_to_exclude",
    ]

    for include_str in include:
        assert include_str in result_index

    for exclude_str in exclude:
        assert exclude_str not in result_index


def test_simplify_names():
    import pandas as pd

    from ramble.reports import (
        clean_redundant_prefixes,
        simplify_experiment_names,
        simplify_names,
    )

    # 1. Simple prefix stripping
    assert simplify_names(["gromacs.water.exp1", "gromacs.water.exp2"]) == ["exp1", "exp2"]

    # 2. Prefix and suffix stripping
    assert simplify_names(["gromacs.water.exp1.ppn_8", "gromacs.water.exp2.ppn_8"]) == [
        "exp1",
        "exp2",
    ]

    # 3. No dots/common parts
    assert simplify_names(["exp1", "exp2"]) == ["exp1", "exp2"]

    # 4. Single element
    assert simplify_names(["gromacs.water.exp1"]) == ["gromacs.water.exp1"]

    # 5. Completely identical elements
    assert simplify_names(["a.b.c", "a.b.c"]) == ["a.b.c", "a.b.c"]

    # 6. Partial mismatch/empty parts fallback
    assert simplify_names(["a.b", "a.b", "a.c"]) == ["b", "b", "c"]

    # 7. Prefix/workload redundant part stripping
    assert (
        clean_redundant_prefixes(
            "osu_micro_benchmarks_osu_allreduce_test_mpi_2_2",
            "osu_micro_benchmarks",
            "osu_allreduce",
        )
        == "test_mpi_2_2"
    )

    assert (
        clean_redundant_prefixes(
            "osu-micro-benchmarks_osu-allreduce_test_mpi_2_2",
            "osu-micro-benchmarks",
            "osu-allreduce",
        )
        == "test_mpi_2_2"
    )

    # Redundant prefix substring test (workload_name contains application_name)
    assert (
        clean_redundant_prefixes(
            "osu_osu_allreduce_test",
            "osu",
            "osu_allreduce",
        )
        == "test"
    )

    # 8. DataFrame simplification (user scenario)
    df = pd.DataFrame(
        {
            "application_name": ["osu_micro_benchmarks"],
            "workload_name": ["osu_allreduce"],
        },
        index=[
            "osu_micro_benchmarks.osu_allreduce.osu_micro_benchmarks_osu_allreduce_test_mpi_2_2"
        ],
    )
    df, prefix = simplify_experiment_names(df)
    assert df.index.tolist() == ["test_mpi_2_2"]
    assert prefix == "osu_micro_benchmarks.osu_allreduce.osu_micro_benchmarks_osu_allreduce_"

    # 9. get_common_stripped_prefix
    from ramble.reports import get_common_stripped_prefix

    assert get_common_stripped_prefix(["a.b.c_1", "a.b.c_2"], ["1", "2"]) == "a.b.c_"
    assert get_common_stripped_prefix(["a.b.c.x.y", "a.b.d.x.y"], ["c", "d"]) == "a.b."

    # 10. Collision Fallback
    df_collision = pd.DataFrame(
        {
            "application_name": ["b", "c"],
            "workload_name": ["", ""],
        },
        index=["a.b.x", "a.c.x"],
    )
    df_collision, prefix = simplify_experiment_names(df_collision)
    assert df_collision.index.tolist() == ["a.b.x", "a.c.x"]
    assert prefix == ""


def test_fom_plot_with_simplify_names(mutable_mock_workspace_path, tmpdir_factory):
    report_name = "unit_test_simplify"
    report_dir_path = tmpdir_factory.mktemp(report_name)
    pdf_path = os.path.join(report_dir_path, f"{report_name}.pdf")

    plot = ramble.reports.FomPlot(
        None, False, report_dir_path, single_experiments, False, False, None, simplify_names=True
    )
    with PdfPages(pdf_path) as pdf_report:
        plot.generate_plot_data(pdf_report)

    assert os.path.isfile(pdf_path)
    assert os.path.isfile(os.path.join(report_dir_path, "foms_fom_1_by_experiments.png"))
