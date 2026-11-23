# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import csv
import unittest
from unittest.mock import MagicMock, patch

from ramble.results_table import ResultsColumn, ResultsTable, ResultsTables


class TestResultsColumn(unittest.TestCase):
    def test_init(self):
        conf_dict = {
            "name": "test_column",
            "expression": "{var}",
            "where": ["'{var}' == 'value'"],
        }
        column = ResultsColumn(conf_dict)
        self.assertEqual(column.name, "test_column")
        self.assertEqual(column.expression, "{var}")
        self.assertEqual(column.where, ["'{var}' == 'value'"])
        self.assertIsNone(column.figure_of_merit)

    @patch("ramble.results_table.logger.die")
    def test_init_both_expression_and_fom(self, mock_die):
        conf_dict = {
            "name": "test_column",
            "expression": "{var}",
            "figure_of_merit": "fom_name",
        }
        ResultsColumn(conf_dict)
        mock_die.assert_called_once()

    @patch("ramble.results_table.logger.die")
    def test_init_missing_expression_and_fom(self, mock_die):
        conf_dict = {"name": "test_column"}
        ResultsColumn(conf_dict)
        mock_die.assert_called_once()

    def test_col_name(self):
        conf_dict = {"name": "col_{var}", "expression": "{var}"}
        column = ResultsColumn(conf_dict)
        app_inst = MagicMock()
        app_inst.expander.expand_var.return_value = "col_value"
        self.assertEqual(column.col_name(app_inst), "col_value")
        app_inst.expander.expand_var.assert_called_with("col_{var}")

    def test_extract_value_expression(self):
        conf_dict = {"name": "test", "expression": "{var}"}
        column = ResultsColumn(conf_dict)
        app_inst = MagicMock()
        app_inst.expander.evaluate_predicate.return_value = True
        app_inst.expander.expand_var.return_value = "expanded_value"
        value = column.extract_value(app_inst)
        self.assertEqual(value, "expanded_value")

    def test_extract_value_fom(self):
        conf_dict = {
            "name": "test",
            "figure_of_merit": "fom_name",
            "figure_of_merit_context": "fom_context",
            "figure_of_merit_origin_type": "fom_origin",
        }
        column = ResultsColumn(conf_dict)
        app_inst = MagicMock()
        app_inst.expander.evaluate_predicate.return_value = True
        app_inst.expander.expand_var.side_effect = lambda x: x
        app_inst.result.contexts = [
            {
                "name": "fom_context",
                "foms": [
                    {
                        "name": "fom_name",
                        "origin_type": "fom_origin",
                        "value": "fom_value",
                    }
                ],
            }
        ]
        value = column.extract_value(app_inst)
        self.assertEqual(value, "fom_value")

    def test_extract_value_where_fails(self):
        conf_dict = {"name": "test", "expression": "{var}", "where": ["'a' == 'b'"]}
        column = ResultsColumn(conf_dict)
        app_inst = MagicMock()
        app_inst.expander.evaluate_predicate.return_value = False
        value = column.extract_value(app_inst)
        self.assertIsNone(value)


class TestResultsTable(unittest.TestCase):
    def setUp(self):
        self.conf_dict = {
            "name": "test_table",
            "columns": [
                {"name": "col1", "expression": "{var1}"},
                {"name": "col2", "figure_of_merit": "fom1"},
            ],
            "group_by": "col1",
            "sort_by": ["col2"],
            "where": ["'{var1}' != 'skip'"],
        }
        self.table = ResultsTable(self.conf_dict)

    def test_init(self):
        self.assertEqual(self.table.name, "test_table")
        self.assertEqual(len(self.table.columns), 2)
        self.assertEqual(self.table.group_by, ["col1"])
        self.assertEqual(self.table.sort_by, ["col2"])
        self.assertEqual(self.table.where, ["'{var1}' != 'skip'"])

    def test_add_where(self):
        self.table.add_where("'new_cond' == 'true'")
        self.assertIn("'new_cond' == 'true'", self.table.where)
        self.table.add_where(["'cond2'"])
        self.assertIn("'cond2'", self.table.where)

    def test_extract_row(self):
        app_inst = MagicMock()
        app_inst.expander.evaluate_predicate.return_value = True
        app_inst.expander.expand_var.side_effect = lambda x, **kwargs: x.strip("{}")
        app_inst.result.contexts = [{"name": "ctx", "foms": [{"name": "fom1", "value": "val2"}]}]

        with patch.object(ResultsColumn, "extract_value", side_effect=["val1", "val2"]):
            self.table.extract_row(app_inst)

        self.assertEqual(self.table._num_rows, 1)
        self.assertEqual(self.table._data["col1"], ["val1"])
        self.assertEqual(self.table._data["col2"], ["val2"])

    @patch("ramble.results_table.create_symlink")
    @patch("ramble.results_table.import_pandas")
    def test_to_csv(self, mock_import_pandas, mock_symlink):
        self.table._data = {"col1": ["a", "b"], "col2": [1, 2]}
        self.table._num_rows = 2

        mock_pd_module = MagicMock()
        mock_import_pandas.return_value = mock_pd_module
        mock_df_constructor = MagicMock()
        mock_pd_module.DataFrame = mock_df_constructor

        mock_df_instance = mock_df_constructor.return_value
        mock_df_instance.groupby.return_value.max.return_value = mock_df_instance
        mock_df_instance.sort_values.return_value = mock_df_instance

        self.table.to_csv("/tmp", "timestamp")

        mock_df_constructor.assert_called_with(self.table._data)
        mock_df_instance.to_csv.assert_called_with("/tmp/test_table.timestamp.csv", index=False)
        mock_symlink.assert_called_with(
            "/tmp/test_table.timestamp.csv", "/tmp/test_table.latest.csv"
        )


class TestResultsTables(unittest.TestCase):
    def setUp(self):
        self.tables = ResultsTables()

    def test_add_table_template(self):
        conf = {"name": "new_table", "columns": []}
        table = self.tables.add_table_template(conf)
        self.assertIsInstance(table, ResultsTable)
        self.assertIn(table, self.tables.table_templates)

    def test_build_tables(self):
        table1 = MagicMock()
        table2 = MagicMock()
        self.tables.table_templates = [table1, table2]

        exp1 = (None, MagicMock(), None)
        exp2 = (None, MagicMock(), None)
        experiment_set = MagicMock()
        experiment_set.all_experiments.return_value = [exp1, exp2]

        filters = MagicMock()

        self.tables.build_tables(experiment_set, filters)

        for table in self.tables.tables.values():
            self.assertEqual(table.extract_row.call_count, 2)

    def test_output_tables(self):
        table1 = MagicMock()
        table1.to_csv.return_value = ("file1.csv", "file1.latest.csv")
        table2 = MagicMock()
        table2.to_csv.return_value = ("file2.csv", "file2.latest.csv")
        self.tables.tables = {"table1": table1, "table2": table2}

        with patch("ramble.util.logger.logger.all_msg") as mock_log:
            self.tables.output_tables("/tmp", "timestamp")

        table1.to_csv.assert_called_with("/tmp", "timestamp")
        table2.to_csv.assert_called_with("/tmp", "timestamp")
        self.assertGreater(mock_log.call_count, 0)


def test_group_by_multiple_columns(tmp_path):
    table = ResultsTable(
        {
            "name": "multi_group",
            "group_by": ["app", "workload"],
            "group_method": "min",
            "sort_by": ["app", "workload"],
        }
    )
    table._data = {
        "app": ["app1", "app1", "app1", "app2", "app2"],
        "workload": ["wl1", "wl1", "wl2", "wl1", "wl1"],
        "score": ["30", "10", "50", "40", "20"],
    }
    table._num_rows = 5

    file_path, _ = table.to_csv(tmp_path, "ts")
    with open(file_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows == [
        {"app": "app1", "workload": "wl1", "score": "10"},
        {"app": "app1", "workload": "wl2", "score": "50"},
        {"app": "app2", "workload": "wl1", "score": "20"},
    ]


if __name__ == "__main__":
    unittest.main()
