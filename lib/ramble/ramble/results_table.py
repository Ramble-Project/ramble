# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
import os
from typing import Any, Dict, List, Optional

from ramble.util.file_util import create_symlink
from ramble.util.logger import logger
from ramble.util.module_utils import import_pandas
from ramble.util.naming import match_pattern


class ResultsColumn:
    """Class representing a single column in a results table"""

    _where_name = "where"
    _column_attrs = [
        "name",
        "expression",
        "figure_of_merit",
        "figure_of_merit_context",
        "figure_of_merit_origin_type",
    ]

    name: Optional[str] = None
    expression: Optional[str] = None
    figure_of_merit: Optional[str] = None
    figure_of_merit_context: Optional[str] = None
    figure_of_merit_origin_type: Optional[str] = None
    _template: Optional["ResultsAutoColumn"] = None

    def __init__(self, conf_dict):
        """Construct a column from a configuration dict, assuming the structure matches the
        column schema in lib/ramble/ramble/schema/tables.py

        Args:
            conf_dict (dict): dictionary structured like the column schema in tables.py

        """
        # Extract column attributes
        for attr in self._column_attrs:
            val = conf_dict.get(attr)
            if val is not None:
                val = str(val)
            setattr(self, attr, val)

        if self.expression and self.figure_of_merit:
            logger.die(
                "Results columns cannot have both 'expression' and 'figure_of_merit' attributes"
            )

        if not self.expression and not self.figure_of_merit:
            logger.die(
                "One of either 'expression' or 'figure_of_merit' are required for each "
                "column definition"
            )

        self.where = []
        if self._where_name in conf_dict:
            self.where.extend(conf_dict[self._where_name])

        # Internal attributes for context columns
        self._context_def_name = conf_dict.get("_context_def_name")
        self._context_vars = conf_dict.get("_context_vars")

    def col_name(self, app_inst):
        """Expand this columns name based on the current experiment

        Args:
            app_inst: Instance of an application class to expand name with

        Returns:
            str: Expanded column name
        """
        return app_inst.expander.expand_var(self.name)

    def extract_value(self, app_inst, extra_vars=None):
        """Extract this column's value based on an application instance and other column values

        Args:
            app_inst: Instance of an application class
            extra_vars: Dictionary containing additional variables to expand with

            iteration (Union[None, str]): The iteration to search for.
            instance (Union[None, str]): The instance to search for.
        """
        if extra_vars is None:
            extra_vars = {}

        value = None

        action_experiment = True
        for expression in self.where:
            if not app_inst.expander.evaluate_predicate(expression):
                action_experiment = False

        if not action_experiment:
            return value

        if self.expression:
            value = app_inst.expander.expand_var(self.expression, extra_vars=extra_vars)
        elif self.figure_of_merit:
            fom_name = self.figure_of_merit
            context_name = None
            if self.figure_of_merit_context:
                context_name = app_inst.expander.expand_var(self.figure_of_merit_context)

            origin_type = None
            if self.figure_of_merit_origin_type:
                origin_type = app_inst.expander.expand_var(self.figure_of_merit_origin_type)

            results = app_inst.result
            for context in results.contexts:
                if (context_name is None or context_name == context["name"]) and (
                    self._context_def_name is None
                    or self._context_def_name == context.get("context_def_name")
                ):
                    match_vars = True
                    if self._context_vars is not None:
                        # Ensure all original context vars match.
                        # Regex groups in self._context_vars don't need to match
                        # because they aren't in context.get('context_vars')
                        c_vars = context.get("context_vars", {})
                        for k, v in c_vars.items():
                            if self._context_vars.get(k) != v:
                                match_vars = False
                                break

                    if match_vars:
                        for fom in context["foms"]:
                            if fom["name"] == fom_name:
                                keep = True
                                if origin_type and origin_type != fom["origin_type"]:
                                    keep = False

                                if keep:
                                    if value is not None:
                                        logger.warn(
                                            "Non-unique values found " f"for column {self.name}"
                                        )
                                    value = fom["value"]
        return value


class ResultsAutoColumn:
    """Class representing a template for auto-generated columns"""

    _where_name = "where"
    _sort_by_name = "sort_by"
    _column_attrs = [
        "name",
        "context_name",
        "figure_of_merit",
        "figure_of_merit_origin_type",
    ]

    name: Optional[str] = None
    context_name: Optional[str] = None
    figure_of_merit: Optional[str] = None
    figure_of_merit_origin_type: Optional[str] = None

    def __init__(self, conf_dict):
        """Construct an auto column from a configuration dict

        Args:
            conf_dict (dict): dictionary structured like the autocolumn schema
        """
        # Extract column attributes
        for attr in self._column_attrs:
            val = conf_dict.get(attr)
            if val is not None:
                val = str(val)
            setattr(self, attr, val)

        self.where = []
        if self._where_name in conf_dict:
            self.where.extend(conf_dict[self._where_name])

        self.sort_by = []
        if self._sort_by_name in conf_dict:
            if isinstance(conf_dict[self._sort_by_name], list):
                self.sort_by.extend(conf_dict[self._sort_by_name])
            else:
                self.sort_by.append(conf_dict[self._sort_by_name])


class ResultsTable:
    """A single results table based on the tables.py schema"""

    _default_group_method = "max"
    _group_method_name = "group_method"
    _group_by_name = "group_by"
    _sort_by_name = "sort_by"
    _columns_name = "columns"
    _autocolumns_name = "autocolumns"
    _where_name = "where"
    _transpose_name = "transpose"

    group_by: List[str]
    sort_by: List[str]

    def __init__(self, conf_dict):
        """Constructor for a single table

        Args:
            conf_dict (dict): Configuration dictionary based on the table schema in tables.py
        """
        self._num_rows = 0
        self._data = {}

        self.name = conf_dict["name"]

        self.group_method = self._default_group_method
        if self._group_method_name in conf_dict:
            self.group_method = conf_dict[self._group_method_name]

        # Build group_by and sort_by attrs
        for set_name in ["group", "sort"]:
            temp_list = []
            set_name_attr = getattr(self, f"_{set_name}_by_name")
            if set_name_attr in conf_dict:
                if isinstance(conf_dict[set_name_attr], list):
                    temp_list.extend(conf_dict[set_name_attr])
                else:
                    temp_list.append(conf_dict[set_name_attr])
            setattr(self, f"{set_name}_by", temp_list)

        # Build table where statements
        self.where = []
        if self._where_name in conf_dict:
            self.where.extend(conf_dict[self._where_name])

        self.transpose = False
        if self._transpose_name in conf_dict:
            self.transpose = conf_dict[self._transpose_name]

        # Build table columns
        self.columns = []
        if self._columns_name in conf_dict:
            for column_config in conf_dict[self._columns_name]:
                self.columns.append(ResultsColumn(column_config))

        # Build table auto columns
        self.autocolumns = []
        if self._autocolumns_name in conf_dict:
            for column_config in conf_dict[self._autocolumns_name]:
                self.autocolumns.append(ResultsAutoColumn(column_config))

        self.generated_columns = {}

    def render(self, app_inst):
        new_table = copy.deepcopy(self)
        new_table.name = app_inst.expander.expand_var(self.name)
        return new_table

    def table_name(self, app_inst):
        """Determine the name for this table, based on a given experiment

        Args:
            app_inst: Instance of an application class

        Returns:
            str: Name of table
        """

        return app_inst.expander.expand_var(self.name)

    def add_where(self, expressions):
        """Add a where expression to this table

        Args:
            expression (Union[List[str], str]): The regular expression to search for.
        """

        if not expressions:
            return

        if isinstance(expressions, list):
            self.where.extend(expressions)
        else:
            self.where.append(expressions)

    def includes_experiment(self, app_inst):
        """Determine if an experiment is included in this table.

        Args:
            app_inst: Instance of an application class

        Returns:
            bool: ``True`` if the app_inst is included in table, ``False`` otherwise
        """

        include_experiment = True

        for expression in self.where:
            if not app_inst.expander.evaluate_predicate(expression):
                include_experiment = False

        return include_experiment

    def extract_row(self, app_inst):
        """Extract a row of data from an experiment

        Args:
            app_inst: Instance of an application class to extract data from
        """

        # Perform discovery for auto columns
        manual_col_names = {c.col_name(app_inst) for c in self.columns}
        for autocol_template in self.autocolumns:
            action_column = True
            for expression in autocol_template.where:
                if not app_inst.expander.evaluate_predicate(expression):
                    action_column = False

            if not action_column:
                continue

            for context in app_inst.result.contexts:
                # Try matching against context_def_name first (the type of context)
                matched_ctx, ctx_groups = match_pattern(
                    autocol_template.context_name, context.get("context_def_name", "")
                )

                # If no match, try matching against the instance name (the output name)
                if not matched_ctx:
                    matched_ctx, ctx_groups = match_pattern(
                        autocol_template.context_name, context.get("name", "")
                    )

                if matched_ctx:
                    context_vars = context.get("context_vars", {}).copy()
                    context_vars.update(ctx_groups)

                    for fom in context["foms"]:
                        matched_fom, fom_groups = match_pattern(
                            autocol_template.figure_of_merit, fom["name"]
                        )
                        if matched_fom:
                            temp_vars = context_vars.copy()
                            temp_vars.update(fom_groups)
                            temp_vars["fom_name"] = fom["name"]
                            temp_vars["context_name"] = context.get("name")

                            col_name = app_inst.expander.expand_var(
                                autocol_template.name, extra_vars=temp_vars
                            )

                            if (
                                col_name not in manual_col_names
                                and col_name not in self.generated_columns
                            ):
                                combined_vars = context.get("context_vars", {}).copy()
                                combined_vars.update(ctx_groups)
                                combined_vars.update(fom_groups)
                                combined_vars["context_name"] = context.get("name")
                                conf_dict = {
                                    "name": col_name,
                                    "figure_of_merit": fom["name"],
                                    "figure_of_merit_context": context["name"],
                                    "figure_of_merit_origin_type": (
                                        autocol_template.figure_of_merit_origin_type
                                    ),
                                    "where": autocol_template.where,
                                    "_context_def_name": context.get("context_def_name"),
                                    "_context_vars": combined_vars,
                                }
                                col_obj = ResultsColumn(conf_dict)
                                col_obj._template = autocol_template
                                self.generated_columns[col_name] = col_obj

        column_values: Dict[str, Any] = {}
        remaining_columns = set(self._data.keys())

        # Combine manual and generated columns
        all_columns = self.columns.copy()

        # Group generated columns by template to apply variable-based sorting if specified
        for autocol_template in self.autocolumns:
            template_cols = [
                col
                for col in self.generated_columns.values()
                if getattr(col, "_template", None) is autocol_template
            ]

            if autocol_template.sort_by:

                def sort_key(col, template=autocol_template):
                    key = []
                    for var in template.sort_by:
                        val = col._context_vars.get(var) if col._context_vars else None
                        try:
                            val = float(val) if val is not None else float("-inf")
                        except (ValueError, TypeError):
                            val = str(val) if val is not None else ""
                        # Use a tuple of (type_flag, value) to prevent comparison errors
                        # between strings and floats in Python 3
                        type_flag = 0 if isinstance(val, (int, float)) else 1
                        key.append((type_flag, val))
                    return tuple(key)

                template_cols.sort(key=sort_key)

            all_columns.extend(template_cols)

        # Re-order self._data to ensure columns appear in the correct sorted order
        new_data = {}
        for column in all_columns:
            col_name = column.col_name(app_inst)
            if col_name in self._data:
                new_data[col_name] = self._data[col_name]

        for k, v in self._data.items():
            if k not in new_data:
                new_data[k] = v
        self._data = new_data

        for column in all_columns:
            col_value = column.extract_value(app_inst, extra_vars=column_values)

            if col_value is None:
                continue

            col_name = column.col_name(app_inst)

            if col_name in remaining_columns:
                remaining_columns.remove(col_name)
                self._data[col_name].append(col_value)

            elif col_name not in self._data:
                self._data[col_name] = [None] * self._num_rows + [col_value]

            column_values[col_name] = col_value

        for col_name in remaining_columns:
            self._data[col_name].append(None)

        self._num_rows += 1

    def _to_dataframe(self):
        """Construct a pandasdata frame from this table's data"""
        pd = import_pandas()
        self._df = pd.DataFrame(self._data)

        for column in self._df.columns:
            try:
                self._df[column] = pd.to_numeric(self._df[column])
            except ValueError:
                pass

        if self.transpose:
            self._df = self._df.transpose()
            # If transposed, the original columns become the index,
            # and rows become columns.
            # We might want to reset the index if we want it as a column,
            # but usually transpose in CSV means just flipping it.

    def _group_dataframe(self):
        """Apply any grouping to this pandas dataframe"""
        if self.group_by and not self.transpose:
            try:
                grouped_df = self._df.groupby(*self.group_by, as_index=False)

                group_func = getattr(grouped_df, self.group_method, grouped_df.max)
                self._df = group_func()
            except KeyError:
                pass

    def _sort_dataframe(self):
        """Apply any sorting to this pandas dataframe"""
        if self.sort_by and not self.transpose:
            try:
                self._df = self._df.sort_values(by=self.sort_by)
            except KeyError:
                pass

    def to_csv(self, directory, timestamp):
        """CSV converter for results table

        Args:
            directory (str): Directory to write tabular data into
            timestamp (str): Timestamp to apply to table output files
        """
        self._to_dataframe()
        self._group_dataframe()
        self._sort_dataframe()

        extension = "csv"
        inner_delim = "."
        filename = self.name + inner_delim + timestamp + inner_delim + extension
        latestname = self.name + inner_delim + "latest" + inner_delim + extension
        file_path = os.path.join(directory, filename)
        latest_path = os.path.join(directory, latestname)
        # If transposed, we might want the index to be written as the first column
        self._df.to_csv(file_path, index=self.transpose)

        create_symlink(file_path, latest_path)
        return file_path, latest_path


class ResultsTables:
    """Class representing a set of results tables"""

    def __init__(self):
        self.table_templates = []
        self.tables = {}

    @property
    def num_tables(self):
        return len(self.table_templates)

    def add_table_template(self, table_conf):
        """Construct a new results table, and add to this set of tables

        Args:
            table_conf (dict): Dictionary configuration of table,
                               assuming table schema from tables.py

        Returns:
            ramble.results_table.ResultsTable: New table instance
        """
        new_table = ResultsTable(table_conf)
        self.table_templates.append(new_table)
        return new_table

    def build_tables(self, experiment_set, filters):
        """Extract data for each table in this set

        Args:
            experiment_set: Set of experiments to extract data from
            filters: Filter object to downselect experiments
        """
        for _, app_inst, _ in experiment_set.filtered_experiments(filters):
            for table_template in self.table_templates:
                if table_template.includes_experiment(app_inst):
                    table_name = table_template.table_name(app_inst)

                    if table_name not in self.tables:
                        self.tables[table_name] = table_template.render(app_inst)

                    self.tables[table_name].extract_row(app_inst)

    def output_tables(self, directory, timestamp):
        """Output tabular data for each of the tables in this set

        Args:
            directory (str): Directory to write tables into
            timestamp (str): Timestamp to apply to table output files
        """
        table_files = []
        table_symlinks = []
        for table in self.tables.values():
            table_file, table_symlink = table.to_csv(directory, timestamp)
            table_files.append(table_file)
            table_symlinks.append(table_symlink)

        if table_files:
            logger.all_msg("Tables written:")
            for file in table_files:
                logger.all_msg(f"  {file}")

            logger.all_msg("Table symlinks updated:")
            for symlink in table_symlinks:
                logger.all_msg(f"  {symlink}")
