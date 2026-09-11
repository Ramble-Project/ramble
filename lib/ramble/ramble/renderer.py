# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import itertools
from typing import Any, Dict, Set

import ramble.expander
import ramble.repeats
import ramble.util.matrices
from ramble.namespace import namespace
from ramble.util.logger import logger


class RenderGroup:
    _obj_types = ["experiment", "package", "environment"]
    _actions = ["create", "exclude"]

    def __init__(self, obj_type=None, action="create"):
        """Constructor for a RenderGroup.

        Create a RenderGroup object, defining several the input to
        a Renderer object.
        """
        if obj_type == "experiment":
            self.object = "experiment"
            self.objects = "experiments"
            self.context = "experiment_name"
        elif obj_type == "package":
            self.object = "package"
            self.objects = "packages"
            self.context = "package_name"
        elif obj_type == "environment":
            self.object = "environment"
            self.objects = "environments"
            self.context = "environment_name"
        else:
            logger.die(
                f"Object type {obj_type} is not valid to render.\n"
                + f"Valid options are: {self._obj_types}"
            )

        if action not in self._actions:
            logger.die(
                f"Action {action} is not valid to render.\n"
                + f"Valid options are: {self._actions}"
            )
        self.action = action

        self.variables = {}
        self.zips = {}
        self.matrices = []
        self.used_variables = set()
        self.n_repeats = 0

    def copy_contents(self, in_group):
        """Copy contents of in_group into self"""

        if in_group.variables:
            self.variables.update(in_group.variables)

        if in_group.zips:
            self.zips.update(in_group.zips)

        if in_group.matrices:
            self.matrices.extend(in_group.matrices)

        if in_group.used_variables:
            self.used_variables = in_group.used_variables.copy()

    def from_dict(self, name_template, in_dict):
        """Extract RenderGroup definitions from a dictionary

        Dictionaries should follow the below format:

        in_dict = {
            'variables': {},
            'zips': {},
            'matrix': [],
            'matrices': {} or []
            }

        Args:
            name_template (str): The name template for the objects this group represents
            in_dict (dict): A dictionary representing the group definitions

        Returns:
            bool: ``True`` if anything was extracted from the dictionary
        """

        extracted = False

        if namespace.variables in in_dict:
            self.variables.update(in_dict[namespace.variables])
            extracted = True

        if namespace.zips in in_dict:
            self.zips.update(in_dict[namespace.zips])
            extracted = True

        self.matrices = ramble.util.matrices.extract_matrices(
            f"{self.action} {self.object}", name_template, in_dict
        )

        if self.matrices:
            extracted = True

        return extracted


class Renderer:
    def _expand_variables(self, variables, expander):
        object_variables = {}
        for name, unexpanded in variables.items():
            if isinstance(unexpanded, dict):
                unexpanded = dict(unexpanded)
                variables[name] = unexpanded
            object_variables[name] = expander.expand_lists(unexpanded)
        return object_variables

    def _expand_zip_and_matrix_members(self, matrices, zips, expander):
        if matrices:
            for matrix in matrices:
                for i, unexpanded_var in enumerate(matrix):
                    var = expander.expand_var(unexpanded_var)
                    matrix[i] = var
        if zips:
            for group_def in zips.values():
                for i, unexpanded_var in enumerate(group_def):
                    group_def[i] = expander.expand_var(unexpanded_var)

    def _filter_used_variables(self, matrices, zips, used_variables):
        if matrices:
            for matrix in matrices:
                for mat_var in matrix:
                    used_variables.add(mat_var)

        # Update zip definitions based on variables that are used.
        # If a zip has one variable that is used, the entire zip is
        # considered used.
        # If a zip contains no used variables, ignore the entire zip.
        if zips:
            remove_zips = set()
            for zip_group, vars_list in zips.items():
                if zip_group in used_variables or any(v in used_variables for v in vars_list):
                    used_variables.update(vars_list)
                else:
                    remove_zips.add(zip_group)

            for zip_name in remove_zips:
                del zips[zip_name]

    def _process_zips(self, render_group, object_variables, zips, zipped_vars):
        defined_zips: Dict[str, Dict[str, Any]] = {}
        for zip_group, group_def in zips.items():
            defined_zips[zip_group] = {"vars": {}, "length": 0}
            cur_zip = defined_zips[zip_group]

            for var_name in group_def:
                if var_name not in object_variables:
                    logger.die(
                        f"An undefined variable {var_name} " f"is defined in zip {zip_group}"
                    )

                if var_name in zipped_vars:
                    logger.die(
                        f"Variable {var_name} is used "
                        "across multiple zips.\n"
                        "Ensure it is only used in a single zip"
                    )

                val = object_variables[var_name]
                if not isinstance(val, list):
                    logger.die(
                        f"Variable {var_name} in zip {zip_group} " "does not refer to a vector."
                    )

                if not val:
                    logger.die(
                        f"Variable {var_name} in zip {zip_group} " "has an invalid length of 0"
                    )

                cur_len = len(val)
                if cur_zip["length"] == 0:
                    cur_zip["length"] = cur_len
                elif cur_len != cur_zip["length"]:
                    logger.die(
                        f"Variable {var_name} in zip {zip_group}\n"
                        f"has a length of {cur_len} which differs "
                        "from the current max of "
                        f'{cur_zip["length"]}'
                    )

                zipped_vars.add(var_name)
                cur_zip["vars"][var_name] = val
                del object_variables[var_name]
        return defined_zips

    def _process_single_matrix(
        self, matrix, matrix_vars, object_variables, defined_zips, consumed_zips, render_group
    ):
        matrix_size = 1
        vectors = []
        variable_names = []
        for var in matrix:
            if var in matrix_vars:
                logger.die(
                    f"Variable {var} has been used in multiple matrices.\n"
                    + "Ensure each variable is only used once across all matrices"
                )
            matrix_vars.add(var)

            if var in object_variables:
                if not isinstance(object_variables[var], list):
                    err_context = object_variables[render_group.context]
                    logger.die(
                        f"In {render_group.object} {err_context}"
                        + f" variable {var} does not refer to a vector."
                    )

                matrix_size = matrix_size * len(object_variables[var])
                vectors.append(object_variables[var])
                variable_names.append(var)

                # Remove the variable, so it's not processed as a vector anymore.
                del object_variables[var]

            elif var in defined_zips:
                zip_len = defined_zips[var]["length"]
                idx_vector = list(range(zip_len))

                matrix_size = matrix_size * zip_len
                vectors.append(idx_vector)
                variable_names.append(var)
                consumed_zips.add(var)
            else:
                err_context = object_variables[render_group.context]
                logger.die(
                    f"In {render_group.object} {err_context}"
                    + f" variable or zip {var} has not been defined yet."
                )
        return matrix_size, vectors, variable_names

    def _create_matrix_generator(self, matrix_variables, defined_zips, matrix_product_iters):
        matrix_col_maps = []
        for names in matrix_variables:
            col_map = []
            for name in names:
                if name in defined_zips:
                    zip_info = defined_zips[name]
                    col_map.append(
                        {
                            "type": "zip",
                            "vars": zip_info["vars"],
                        }
                    )
                else:
                    col_map.append({"type": "var", "name": name})
            matrix_col_maps.append(col_map)

        def _matrix_generator_func():
            for entry_tuple in zip(*matrix_product_iters):
                obj = {}
                for mat_idx, entry in enumerate(entry_tuple):
                    col_map = matrix_col_maps[mat_idx]
                    for name_idx, val in enumerate(entry):
                        # entry is a tuple of indices or values?
                        # Wait, vectors contained:
                        # if var in object_variables:
                        #    vectors.append(object_variables[var]) -> values
                        # if var in defined_zips: vectors.append(idx_vector) -> indices
                        info = col_map[name_idx]
                        if info["type"] == "zip":
                            idx = val
                            for zip_var, zip_vals in info["vars"].items():
                                obj[zip_var] = zip_vals[idx]
                        else:
                            obj[info["name"]] = val
                yield obj

        return _matrix_generator_func()

    def _process_matrices(
        self, render_group, object_variables, matrices, defined_zips, consumed_zips
    ):
        """Matrix syntax is:
        matrix:
        - <var1>
        - <var2>
        - [1, 2, 3, 4] # inline vector
        matrices:
        - matrix_a:
          - <var1>
          - <var2>
        - matrix:b:
          - <var_3>
          - <var_4>

          Matrices consume vector variables.
        """
        last_size = -1
        matrix_vars: Set[str] = set()
        matrix_vectors = []
        matrix_variables = []
        for matrix in matrices:
            matrix_size, vectors, variable_names = self._process_single_matrix(
                matrix, matrix_vars, object_variables, defined_zips, consumed_zips, render_group
            )

            if last_size == -1:
                last_size = matrix_size

            if last_size != matrix_size:
                err_context = object_variables[render_group.context]
                logger.die(
                    f"Matrices defined in {render_group.object} {err_context}"
                    + " do not result in the same number of elements."
                )

            matrix_vectors.append(vectors)
            matrix_variables.append(variable_names)

        matrix_product_iters = [itertools.product(*vectors) for vectors in matrix_vectors]

        return self._create_matrix_generator(matrix_variables, defined_zips, matrix_product_iters)

    def _post_process_zips(self, defined_zips, consumed_zips, object_variables):
        if defined_zips:
            if consumed_zips:
                for zip_group in consumed_zips:
                    if zip_group in defined_zips:
                        del defined_zips[zip_group]

            for zip_name in defined_zips:
                for var, val in defined_zips[zip_name]["vars"].items():
                    object_variables[var] = val

    def _combine_vectors_and_matrices(
        self, render_group, object_variables, used_variables, matrix_generator, ignore_used, fatal
    ):
        vector_vars = {}
        # Extract vector variables
        max_vector_size = 0
        for var, val in object_variables.items():
            if isinstance(val, list) and (var in used_variables or not ignore_used):
                vector_vars[var] = val.copy()
                max_vector_size = max(len(val), max_vector_size)

        if vector_vars:
            # Check that sizes are the same
            length_mismatch = False
            for val in vector_vars.values():
                if len(val) != max_vector_size:
                    length_mismatch = True

            if fatal and length_mismatch:
                err_context = object_variables[render_group.context]
                err_str = (
                    f"Length mismatch in vector variables in {render_group.object} "
                    f"{err_context}\n"
                )
                for var, val in vector_vars.items():
                    err_str += f"\tVariable {var} has length {len(val)}\n"
                logger.die(err_str)

            # Materialize matrix objects if we have vector vars
            matrix_objects = list(matrix_generator) if matrix_generator else None

            # Iterate over the vector length, and set the value in the
            # object dict to the index value.
            def _generator():
                for i in range(max_vector_size):
                    obj_vars = {}
                    for var, val in vector_vars.items():
                        if len(val) > i:
                            obj_vars[var] = val[i]

                    if matrix_objects:
                        for matrix_object in matrix_objects:
                            # Combine vector vars with matrix object
                            # Matrix object overrides vector vars if collision
                            # (though collision shouldn't happen)
                            yield {**obj_vars, **matrix_object}
                    else:
                        yield obj_vars

            return _generator()

        elif matrix_generator:
            return matrix_generator
        else:
            return [{}]

    def _filter_and_yield_objects(
        self, render_group, object_variables, new_objects, exclude_where, n_repeats
    ):
        where_expander = ramble.expander.Expander(object_variables, None)

        for obj in new_objects:
            logger.debug(f"Rendering {render_group.object}:")

            keep_object = True
            if exclude_where:
                for where in exclude_where:
                    try:
                        evaluated = where_expander.evaluate_predicate(where, extra_vars=obj)
                        if evaluated:
                            keep_object = False
                            break
                    except ramble.expander.RambleSyntaxError:
                        # Fail-open to allow for late-binding of variables
                        pass

            if keep_object:
                repeats = ramble.repeats.Repeats()
                if n_repeats > 0:
                    repeats.set_repeats(True, n_repeats)

                yield {**object_variables, **obj}, repeats

    def render_objects(self, render_group, exclude_where=None, ignore_used=True, fatal=True):
        """Render objects based on the input variables and matrices

        Internally collects all matrix and vector variables.

        First, zips are created. Zips extract vector variables, and group them
        into a higher level name.

        Next, matrices are processed. Matrices consume vector variables, or
        explicit zips.

        Vectors in the same matrix are crossed, sibling matrices are zipped.
        All matrices are required to result in the same number of elements, but
        not be the same shape.

        Matrix elements are only allowed to be the names of variables. These
        variables are required to be vectors.

        After matrices are processed, any remaining vectors are zipped
        together. All vectors are required to be of the same size.

        The resulting zip of vectors is then crossed with all of the matrices
        to build a final list of objects.

        After processing the expansion logic, this function yields a dictionary
        of variable definitions, one for each object that would be rendered.

        If n_repeats is defined in input variables, this function yields one base
        and n copies of the rendered variable dictionary.

        Yields:
            - a dictionary of variables for single object definition
            - a Repeats object indicating if rendered object is a repeat and its index

        """
        variables = render_group.variables
        used_variables = render_group.used_variables.copy()

        expander = ramble.expander.Expander(variables, None)

        # Convert all dict types to base dicts
        # This allows the expander to properly return typed dicts.
        # Without this, all dicts are ruamel.CommentedMaps, and these
        # cannot be evaled using ast.literal_eval.
        # Also expand all variables that generate lists
        object_variables = self._expand_variables(variables, expander)

        # Expand zip and matrix members to allow indirections like
        # ```
        # variables:
        #   my_vec: [1, 2, 3]
        #   my_vec_ref: 'my_vec'
        #   matrix:
        #   - '{my_vec_ref}'
        # ```
        zips = render_group.zips.copy()
        matrices = render_group.matrices
        self._expand_zip_and_matrix_members(matrices, zips, expander)

        if ignore_used:
            # Add variables / zips in matrices to used variables.
            # Update zip definitions based on variables that are used.
            # If a zip has one variable that is used, the entire zip is
            # considered used.
            # If a zip contains no used variables, ignore the entire zip.
            self._filter_used_variables(matrices, zips, used_variables)

        # Extract Zips
        defined_zips: Dict[str, Dict[str, Any]] = {}
        consumed_zips: Set[str] = set()
        if zips:
            zipped_vars: Set[str] = set()
            defined_zips = self._process_zips(render_group, object_variables, zips, zipped_vars)

        # Process Matrices
        matrix_generator = None
        if matrices:
            matrix_generator = self._process_matrices(
                render_group, object_variables, matrices, defined_zips, consumed_zips
            )

        # Remove all consumed zips and return all remaining zipped variables
        # back to real vector definitions
        self._post_process_zips(defined_zips, consumed_zips, object_variables)

        # After matrices have been processed, extract any remaining vector variables
        new_objects = self._combine_vectors_and_matrices(
            render_group, object_variables, used_variables, matrix_generator, ignore_used, fatal
        )

        n_repeats = render_group.n_repeats
        yield from self._filter_and_yield_objects(
            render_group, object_variables, new_objects, exclude_where, n_repeats
        )
