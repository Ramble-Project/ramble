# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ast
import collections
import functools
import itertools
import math
import operator
import random
import re
import string
import sys
from contextlib import contextmanager
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Union

import ramble.config
import ramble.error
import ramble.keywords
from ramble.util import naming
from ramble.util.logger import logger
from ramble.util.path import substitute_config_variables

# Regex for detecting math operators or keywords
# We check for: + - * / % ^ & | ~ < > = ( ) [ ] { } , ' "
# And keywords: and, or, in, is, not
_math_regex = re.compile(r"[+\-*/%^&|~<>=()\[\]{},'\"]|\b(?:and|or|in|is|not)\b")
_MATH_CONSTANTS = frozenset(("True", "False", "None"))

# Define a dummy type so that it doesn't match any real types
# These type defs are used to handle compatibility among Python versions
_DUMMY_TYPE = type("_DUMMY_TYPE", (), {})
_AST_CONSTANT = getattr(ast, "Constant", _DUMMY_TYPE)
_AST_NUM = getattr(ast, "Num", _DUMMY_TYPE)
_AST_STR = getattr(ast, "Str", _DUMMY_TYPE)
_AST_NAME_CONSTANT = getattr(ast, "NameConstant", _DUMMY_TYPE)


def _get_source_segment(source, node):
    """Retrieve the source segment for an AST node, with compatibility for Python < 3.8"""
    if hasattr(ast, "get_source_segment"):
        if (
            "\n" not in source
            and hasattr(node, "end_col_offset")
            and node.end_col_offset is not None
            and hasattr(node, "col_offset")
            and node.col_offset is not None
            # Only apply the fast path for ascii-only strings
            and hasattr(source, "isascii")
            and source.isascii()
        ):
            return source[node.col_offset : node.end_col_offset]
        return ast.get_source_segment(source, node)

    # Fallback for Python < 3.8 which lacks end_lineno/end_col_offset
    # This is a best-effort implementation for single-line segments (most literals)
    try:
        if not hasattr(node, "lineno") or not hasattr(node, "col_offset"):
            return None

        lines = source.splitlines(keepends=True)
        line = lines[node.lineno - 1]
        segment = line[node.col_offset :]

        # For numeric literals, we can try to find the end by matching the pattern
        if isinstance(node, (_AST_NUM, _AST_CONSTANT)):
            # Match integers (including hex, octal, binary and underscores)
            # and floats.
            match = re.match(r"[0-9a-zA-Z._]+", segment)
            if match:
                return match.group(0)

        # For strings, we need to handle quotes
        if isinstance(node, (_AST_STR, _AST_CONSTANT)):
            if segment.startswith(("'", '"')):
                quote = segment[0]
                if segment.startswith(f"{quote}{quote}{quote}"):
                    quote = f"{quote}{quote}{quote}"
                # Find the matching end quote, being careful about escapes
                # This is a bit complex, but for many cases re works
                end_match = re.search(rf"{quote}.*?(?<!\\){quote}", segment)
                if end_match:
                    return end_match.group(0)

        return None
    except (IndexError, AttributeError):
        return None


@functools.lru_cache(maxsize=2048)
def _ast_parse(in_str):
    """Parse a string into an AST, with LRU caching."""
    try:
        return ast.parse(in_str, mode="eval")
    except SyntaxError:
        return None


def _and(a, b):
    return a and b


def _or(a, b):
    return a or b


def _join_str(seq, sep=","):
    return sep.join(str(i) for i in seq)


def _re_search(regex, s):
    return re.search(regex, s) is not None


def _file_contains(file_path, pattern):
    import os

    if os.path.isfile(file_path):
        with open(file_path, encoding="utf-8") as f:
            return re.search(pattern, f.read(), re.MULTILINE) is not None
    return False


def _str_replace(s, *args, **kwargs):
    return str(s).replace(*args, **kwargs)


# TODO: These conditional defines should be removed when support for
# older Python versions are dropped.
if sys.version_info >= (3, 8):

    def _is_str_node(node):
        return False

    def _is_num_node(node):
        return False

    def _is_name_constant_node(node):
        return False

else:  # pragma: no cover

    def _is_str_node(node):
        return isinstance(node, _AST_STR)

    def _is_num_node(node):
        return isinstance(node, _AST_NUM)

    def _is_name_constant_node(node):
        return isinstance(node, _AST_NAME_CONSTANT)


if sys.version_info >= (3, 9):

    def _is_index_node(node):
        return False

else:

    def _is_index_node(node):
        return isinstance(node, ast.Index)


def _maybe(expander, var_name, default=""):
    try:
        return expander.expand_var_name(var_name, allow_passthrough=False)
    except RambleSyntaxError:
        return default


supported_math_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.BitXor: operator.xor,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.And: _and,
    ast.Or: _or,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.Invert: operator.invert,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

supported_scalar_function_pointers = {
    "str": str,
    "int": int,
    "float": float,
    "max": max,
    "min": min,
    "ceil": math.ceil,
    "floor": math.floor,
    "log2": math.log2,
    "log10": math.log10,
    "sqrt": math.sqrt,
    "randrange": random.randrange,
    "randint": random.randint,
    "simplify_str": naming.simplify_name,
    "join_str": _join_str,
    "re_search": _re_search,
    "file_contains": _file_contains,
    "replace": _str_replace,
}

# Format Spec Regex:
format_spec_regex = re.compile(r"(?P<kw>[^:]+(?:::[^:]+)*):(?P<format_spec>[^:]+)$")

# Functions that need to be supplied with the expander
supported_scalar_function_with_self_arg_pointers = {
    "maybe": _maybe,
}


supported_list_function_pointers = {
    "range": range,
}


supported_modules = {
    "math": math,
}


formatter = string.Formatter()


class ExpansionDelimiter:
    """Class representing the delimiters for ramble expansion strings"""

    left = "{"
    right = "}"
    escape = "\\"


class VformatDelimiter:
    """Class representing the delimiters for the string.Formatter class"""

    left = "{"
    right = "}"


class ExpansionNode:
    """Class representing a node in a ramble expansion graph"""

    def __init__(self, left_idx, right_idx):
        self.left = left_idx
        self.right = right_idx
        self.children = []
        self.idx = None
        self.contents = None
        self.value = None
        self.root = None

    def __str__(self):
        lines = []
        lines.append("   Node:")
        lines.append(f"      Indices: ({self.left}, {self.right})")
        lines.append(f"      Num Children: ({len(self.children)})")
        lines.append(f'      Contents: "{self.contents}"')
        lines.append(f'      Value: "{self.value}"')
        lines.append(f'      Is root: "{self is self.root}"')
        return "\n".join(lines)

    def relative_indices(self, relative_to):
        """Compute node indices relative to another node

        Args:
            relative_to (ExpansionNode): node to shift current node's indices relative to

        Returns:
            tuple: indices of shifted match set
        """
        return (self.left - relative_to.left, self.right - relative_to.left)

    def add_children(self, children):
        """Add children to this node

        Args:
            children (ExpansionNode | list): nodes to adds as children of self
        """
        if isinstance(children, list):
            self.children.extend(children)
        else:
            self.children.append(children)

    def define_value(
        self,
        expansion_dict,
        allow_passthrough=True,
        expansion_func=str,
        evaluation_func=eval,
        no_expand_vars=None,
        used_vars=None,
        replace_escaped_braces=None,
    ):
        """Define the value for this node.

        Construct the value of self. This builds up a string representation of
        self, and performs evaluation and formatting of the resulting string.
        This includes extracting the values of the children nodes, and
        replacing their values in the proper positions in self's string.

        Stores the resulting value in self.value

        Args:
            expansion_dict (dict): variable definitions to use for expanding
                detected matches
            allow_passthrough (bool): if true, expansion is allowed to fail. if
                false, failed expansion raises an error.
            expansion_func (func): function to use for expansion of nested
                variable definitions
            evaluation_func (func): function to use for evaluating math of
                strings
            no_expand_vars (set): set of variable names that should never be
                expanded
            replace_escaped_braces (bool): Whether escaped curly braces are replaced
                                           as part of expansion or not.
        """
        if no_expand_vars is None:
            no_expand_vars = set()
        if used_vars is None:
            used_vars = set()
        if self.contents is not None:
            parts = []
            last_idx = 0
            for child in self.children:
                child_indices = child.relative_indices(self)
                parts.append(self.contents[last_idx : child_indices[0]])
                parts.append(str(child.value))
                last_idx = child_indices[1] + 1

            if last_idx != len(self.contents):
                parts.append(self.contents[last_idx:])

            if self != self.root:
                replaced_contents = "".join(parts)

                # Special case '{}'
                if len(replaced_contents) == 2:
                    self.value = "{}"
                    return

                keyword = replaced_contents[1:-1]
                format_match = None

                # Only search for format specs if the keyword is not already a variable
                if keyword not in expansion_dict:
                    format_match = format_spec_regex.search(keyword)
                required_passthrough = False

                if format_match:
                    keyword = format_match.group("kw")
                    format_spec = format_match.group("format_spec")

                if keyword in expansion_dict:
                    used_vars.add(keyword)
                    # Exit expansion for variables defined as no_expand
                    if keyword in no_expand_vars:
                        self.value = expansion_dict[keyword]
                        return
                    else:
                        self.value = expansion_func(
                            expansion_dict,
                            expansion_dict[keyword],
                            allow_passthrough=allow_passthrough,
                            replace_escaped_braces=replace_escaped_braces,
                        )
                else:
                    self.value = keyword
                    required_passthrough = True

                # Evaluation should go here
                try:
                    old_value = self.value
                    self.value = evaluation_func(self.value)
                    logger.debug(f"  Expanded: {old_value} -> {self.value}")
                    if old_value != self.value:
                        required_passthrough = False
                except SyntaxError:
                    pass

                # If we had a format spec, add it
                if format_match:
                    kw_dict = {"value": self.value}
                    format_str = f"value:{format_spec}"
                    try:
                        self.value = formatter.vformat(
                            VformatDelimiter.left + format_str + VformatDelimiter.right,
                            [],
                            kw_dict,
                        )
                        required_passthrough = False
                    except ValueError:
                        self.value = replaced_contents[1:-1]
                        required_passthrough = True
                    except KeyError:
                        self.value += replaced_contents[1:-1]
                        required_passthrough = True

                if required_passthrough:
                    self.value = f"{{{self.value}}}"
                    if not allow_passthrough:
                        raise_passthrough_error(self.contents, self.value)
            else:
                replaced_contents = "".join(parts)
                try:
                    self.value = evaluation_func(replaced_contents)
                except SyntaxError:
                    self.value = replaced_contents

                # Replace escaped curly braces with curly braces
                if replace_escaped_braces and isinstance(self.value, str):
                    self.value = self.value.replace("\\{", "{").replace("\\}", "}")


class ExpansionGraph:
    """Class representing a graph of ExpansionNodes"""

    def __init__(self, in_str):
        self.str = in_str
        self.root = ExpansionNode(0, len(in_str) - 1)
        self.root.contents = in_str
        self.root.root = self.root

        opened = []
        children = []
        escaped = False
        for i, c in enumerate(self.str):
            if c == ExpansionDelimiter.left and not escaped:
                opened.append(i)
                children.append([])
            elif c == ExpansionDelimiter.right and len(opened) > 0 and not escaped:
                left_idx = opened.pop()
                right_idx = i

                cur_match = ExpansionNode(left_idx, right_idx)
                cur_match.add_children(children.pop())
                cur_match.contents = self.str[left_idx : right_idx + 1]  # Define contents
                cur_match.root = self.root

                if opened:
                    children[-1].append(cur_match)
                else:
                    self.root.add_children(cur_match)
            elif c == "\n":  # Don't expand across new lines
                opened = []

            if c == ExpansionDelimiter.escape:
                escaped = True
            elif escaped:
                escaped = False

        if opened:
            self.root.add_children(children.pop())

    def walk(self, in_node=None):
        """Perform a DFS walk of the nodes in the graph

        Args:
            in_node (ExpansionNode): node to begin the walk from, if not set uses self.root

        Yields:
            (ExpansionNode): nodes following a DFS traversal of the graph
        """
        cur_node = in_node
        if cur_node is None:
            cur_node = self.root

        for child in cur_node.children:
            yield from self.walk(in_node=child)

        yield cur_node

    def __str__(self):
        lines = []
        lines.append(f"Processing string: {self.str}")
        lines.extend(f"{node}" for node in self.walk())
        return "\n".join(lines)


class Expander:
    """A class that will track and expand keyword arguments

    This class will track variables and their definitions, to allow for
    expansion within string.

    The variables can come from workspace variables, software stack variables,
    and experiment variables.

    Additionally, math will be evaluated as part of expansion.
    """

    _ast_dbg_prefix = "EXPANDER AST:"

    def __init__(self, variables, experiment_set, no_expand_vars=None):
        if no_expand_vars is None:
            no_expand_vars = set()

        self._replace_escaped_braces = True
        self._keywords = ramble.keywords.keywords

        self._variables = variables
        self._no_expand_vars = no_expand_vars
        self._used_variables = set()
        self._used_variable_stage = set()

        self._experiment_set = experiment_set
        self.replacement_paths = {}

        self._math_str_stack = []

        self._application_name = None
        self._application_spec = None
        self._application_version = None
        self._workload_name = None
        self._experiment_name = None

        self._application_namespace = None
        self._workload_namespace = None
        self._experiment_namespace = None
        self._env_path = None

        self._application_input_dir = None
        self._workload_input_dir = None
        self._license_input_dir = None

        self._application_run_dir = None
        self._workload_run_dir = None
        self._experiment_run_dir = None

    def add_no_expand_var(self, var: str):
        """Add a new variable to the no expand set

        Args:
            var (str): Variable that should not expand
        """
        self._no_expand_vars.add(var)

    def set_no_expand_vars(self, no_expand_vars):
        self._no_expand_vars = no_expand_vars.copy()

    def flush_used_variable_stage(self):
        self._used_variable_stage = set()

    def merge_used_variable_stage(self):
        self._used_variables = self._used_variables.union(self._used_variable_stage)
        self.flush_used_variable_stage()

    def copy(self):
        return Expander(
            self._variables.copy(),
            self._experiment_set,
            self._no_expand_vars.copy(),
        )

    @property
    def application_name(self):
        if not self._application_name:
            self._application_name = self.expand_var_name(self._keywords.application_name)

        return self._application_name

    @property
    def application_spec(self):
        if not self._application_spec:
            self._application_spec = self.expand_var_name(self._keywords.application_spec)

        return self._application_spec

    @property
    def application_version(self):
        if not self._application_version:
            self._application_version = self.expand_var_name(self._keywords.application_version)

        return self._application_version

    @property
    def workload_name(self):
        if not self._workload_name:
            self._workload_name = self.expand_var_name(self._keywords.workload_name)

        return self._workload_name

    @property
    def experiment_name(self):
        if not self._experiment_name:
            self._experiment_name = self.expand_var_name(self._keywords.experiment_name)

        return self._experiment_name

    @property
    def application_namespace(self):
        if not self._application_namespace:
            self._application_namespace = self.application_spec

        return self._application_namespace

    @property
    def workload_namespace(self):
        if not self._workload_namespace:
            self._workload_namespace = f"{self.application_spec}.{self.workload_name}"

        return self._workload_namespace

    @property
    def experiment_namespace(self):
        if not self._experiment_namespace:
            self._experiment_namespace = "{}.{}.{}".format(
                self.application_spec,
                self.workload_name,
                self.experiment_name,
            )

        return self._experiment_namespace

    @property
    def env_path(self):
        if not self._env_path:
            var = self.expansion_str(self._keywords.env_path)
            self._env_path = self.expand_var(var)

        return self._env_path

    @property
    def application_input_dir(self):
        if not self._application_input_dir:
            self._application_input_dir = self.expand_var_name(
                self._keywords.application_input_dir
            )

        return self._application_input_dir

    @property
    def workload_input_dir(self):
        if not self._workload_input_dir:
            self._workload_input_dir = self.expand_var_name(self._keywords.workload_input_dir)

        return self._workload_input_dir

    @property
    def license_input_dir(self):
        if not self._license_input_dir:
            self._license_input_dir = self.expand_var_name(self._keywords.license_input_dir)

        return self._license_input_dir

    @property
    def application_run_dir(self):
        if not self._application_run_dir:
            self._application_run_dir = self.expand_var_name(self._keywords.application_run_dir)

        return self._application_run_dir

    @property
    def workload_run_dir(self):
        if not self._workload_run_dir:
            self._workload_run_dir = self.expand_var_name(self._keywords.workload_run_dir)

        return self._workload_run_dir

    @property
    def experiment_run_dir(self):
        if not self._experiment_run_dir:
            self._experiment_run_dir = self.expand_var_name(self._keywords.experiment_run_dir)

        return self._experiment_run_dir

    @contextmanager
    def preserve_escaped_braces(self):
        previous = self._replace_escaped_braces
        self._replace_escaped_braces = False
        try:
            yield
        finally:
            self._replace_escaped_braces = previous

    def expand_lists(self, var):
        """Expand a variable into a list if possible

        If expanding a variable would generate a list, this function will
        return a list. If any error case happens, this function will return
        the unmodified input value.

        NOTE: This function is generally called early in the expansion. This allows
        lists to be generated before rendering experiments, but does not support
        pulling a list from a different experiment.
        """
        try:
            math_ast = _ast_parse(str(var))
            value = self.eval_math(math_ast.body)
        except (MathEvaluationError, AttributeError, ValueError, SyntaxError):
            return var
        else:
            if isinstance(value, list):
                return value
            return var

    def expand_var_name(
        self,
        var_name: str,
        extra_vars: Optional[Dict] = None,
        allow_passthrough: bool = True,
        typed: bool = False,
        merge_used_stage: bool = True,
        replace_escaped_braces: Optional[bool] = None,
    ):
        """Convert a variable name to an expansion string, and expand it

        Take a variable name (var) and convert it to an expansion string by
        calling the expansion_str function. Pass the expansion string into
        expand_var, and return the result.

        Args:
            var_name (str): String name of variable to expand
            extra_vars (dict): Variable definitions to use with highest precedence
            allow_passthrough (bool): Whether the string is allowed to have keywords
                                      after expansion
            typed (bool): Whether the return type should be typed or not
            merge_used_stage (bool): Whether tracked variables are merged into
                                     the used variable set or not.
            replace_escaped_braces (bool): Whether escaped curly braces are replaced
                                           as part of expansion or not.
        """
        return self.expand_var(
            self.expansion_str(var_name),
            extra_vars=extra_vars,
            allow_passthrough=allow_passthrough,
            typed=typed,
            merge_used_stage=merge_used_stage,
            replace_escaped_braces=replace_escaped_braces,
        )

    def expand_var(
        self,
        var: str,
        extra_vars: Optional[Dict] = None,
        allow_passthrough: bool = True,
        typed: bool = False,
        merge_used_stage: bool = True,
        replace_escaped_braces: Optional[bool] = None,
    ):
        """Perform expansion of a string

        Expand a string by building up a dict of all
        expansion variables.

        Args:
            var (str): String variable to expand
            extra_vars (dict): Variable definitions to use with highest precedence
            allow_passthrough (bool): Whether the string is allowed to have keywords
                                      after expansion
            typed (bool): Whether the return type should be typed or not
            merge_used_stage (bool): Whether tracked variables are merged into
                                     the used variable set or not.
            replace_escaped_braces (bool): Whether escaped curly braces are replaced
                                           as part of expansion or not.
        """

        if var is None or var == "None":
            return None if typed else "None"

        if isinstance(var, (int, float, bool)):
            return var if typed else str(var)

        passthrough_setting = allow_passthrough

        # If disable_passthrough is set, override allow_passthrough from caller
        if ramble.config.get("config:disable_passthrough"):
            passthrough_setting = False

        logger.debug(f"BEGINNING OF EXPAND_VAR STACK ON {var}")
        logger.debug(f" REPLACE VAR (1): {replace_escaped_braces}")
        logger.debug(f" REPLACE VAR (2): {self._replace_escaped_braces}")

        if extra_vars:
            expansions = collections.ChainMap(extra_vars, self._variables)
        else:
            expansions = self._variables

        try:
            value = self._partial_expand(
                expansions,
                str(var),
                allow_passthrough=passthrough_setting,
                replace_escaped_braces=replace_escaped_braces,
            )
        except RamblePassthroughError as e:
            if not passthrough_setting:
                raise RambleSyntaxError(
                    f"Encountered a passthrough error while expanding {var}\n"
                    f"{e}\n"
                    "This error means a variable could not be fully expanded and still "
                    "contains variable-style references, which is not allowed in this "
                    "context."
                ) from None

        logger.debug(f"END OF EXPAND_VAR STACK {value}")
        if typed:
            logger.debug(f"BEGINNING OF TYPING ON {value}")
            try:
                value = ast.literal_eval(value)
                logger.debug(f"END OF TYPING {value}")
            except ValueError:
                logger.debug("END OF TYPING Failed with ValueError")
            except SyntaxError:
                logger.debug("END OF TYPING Failed with SyntaxError")

        if merge_used_stage:
            self.merge_used_variable_stage()

        if isinstance(value, str):
            return substitute_config_variables(value, local_replacements=self.replacement_paths)
        else:
            return value

    def evaluate_predicate(self, in_str, extra_vars=None, merge_used_stage: bool = True):
        """Evaluate a predicate by expanding and evaluating math contained in a string

        Args:
            in_str: String representing predicate that should be evaluated
            extra_vars: Variable definitions to use with highest precedence

        Returns:
            bool: ``True`` or ``False`` based on the evaluation of ``in_str``
        """

        evaluated = self.expand_var(
            in_str,
            extra_vars=extra_vars,
            allow_passthrough=False,
            merge_used_stage=merge_used_stage,
        )

        if not isinstance(evaluated, str):
            logger.die("Logical compute failed to return a string")

        if evaluated == "True":
            return True
        elif evaluated == "False":
            return False
        else:
            logger.die(
                f"When evaluating {in_str}, evaluate_predicate returned "
                f'a non-boolean string: "{evaluated}"'
            )

    def satisfies(
        self,
        reqs: Union[str, List[str], FrozenSet[str], None] = None,
        variant_set=None,
        extra_vars=None,
        merge_used_stage: bool = True,
    ):
        """Determine an experiment's variants satisfy a query

        Args:
            reqs: List of string requirements to check if experiment satisfies
            extra_vars: Variable definitions to use with highest precedence
            merged_used_stage: Whether used variables are merged into the
                               set of used variables or not.

        Returns:
            bool: ``True`` or ``False`` based if the experiment's variants satisfy
            the input requirement.
        """
        if reqs is None:
            return True

        variant_definitions = set()

        if hasattr(variant_set, "as_set"):
            for variant in variant_set.as_set(self):
                variant_definitions.add(variant)

        satisfied = True
        if isinstance(reqs, str):
            reqs = [reqs]
        elif isinstance(reqs, frozenset):
            reqs = list(reqs)

        for req in reqs:
            if "@" in req and "=" not in req and "+" not in req and "~" not in req:
                variant_name, _ = req.split("@")
                version = variant_set.version(variant_name)
                if hasattr(version, "satisfies"):
                    satisfied = satisfied and version.satisfies(req)
                else:
                    satisfied = False
            else:
                exp_req = self.expand_var(
                    req, extra_vars=extra_vars, merge_used_stage=merge_used_stage
                )

                satisfied = satisfied and exp_req in variant_definitions
        return satisfied

    @staticmethod
    def expansion_str(in_str):
        return f"{ExpansionDelimiter.left}{in_str}{ExpansionDelimiter.right}"

    def _partial_expand(
        self,
        expansion_vars,
        in_str,
        allow_passthrough=True,
        replace_escaped_braces=None,
    ):
        """Perform expansion of a string with some variables

        args:
          expansion_vars (dict): Variables to perform expansion with
          in_str (str): Input template string to expand
          allow_passthrough (bool): Define if variables are allowed to passthrough
                                    without being expanded.

          replace_escaped_braces (bool): Whether escaped curly braces are replaced
                                         as part of expansion or not.

        Returns:
            str: Expanded version of ``in_str``
        """

        if replace_escaped_braces is None:
            replace_escaped_braces = self._replace_escaped_braces

        if not isinstance(replace_escaped_braces, bool):
            logger.error(
                "Partial expand called with invalid value "
                f"for replace_escaped_braces of {replace_escaped_braces}\n"
                "Value must be a boolean."
            )

        if isinstance(in_str, Enum):
            in_str = in_str.value

        if isinstance(in_str, str):
            if ExpansionDelimiter.left not in in_str and ExpansionDelimiter.right not in in_str:
                return str(self.perform_math_eval(in_str, expansion_vars=expansion_vars))

            str_graph = ExpansionGraph(in_str)
            for node in str_graph.walk():
                node.define_value(
                    expansion_vars,
                    allow_passthrough=allow_passthrough,
                    expansion_func=self._partial_expand,
                    evaluation_func=functools.partial(
                        self.perform_math_eval, expansion_vars=expansion_vars
                    ),
                    no_expand_vars=self._no_expand_vars,
                    used_vars=self._used_variable_stage,
                    replace_escaped_braces=replace_escaped_braces,
                )

            return str(str_graph.root.value)

        return str(in_str)

    def perform_math_eval(self, in_str, expansion_vars=None):
        """Attempt to evaluate in_str

        Args:
            in_str (str): string representing math to attempt to evaluate

        Returns:
            str: either the evaluation of ``in_str`` (if successful) or ``in_str``
            unmodified (if unsuccessful)

        """
        # Fast path for things that are likely paths
        if in_str.startswith(("/", "./")):
            return in_str

        # Heuristic: if no math operators/keywords, it's probably a string. Skip parsing.
        if not _math_regex.search(in_str):
            # If it doesn't match the regex, it's only math-relevant if it's:
            # 1. A number (like 123)
            # 2. A constant (True, False, None)
            # If it has a space, or is a valid identifier (excluding constants), it's not math.
            if " " in in_str or (in_str.isidentifier() and in_str not in _MATH_CONSTANTS):
                return in_str

        math_ast = _ast_parse(in_str)
        if math_ast is None:
            return in_str

        self._math_str_stack.append(in_str)
        try:
            try:
                body = math_ast.body
                out_str = self.eval_math(body, expansion_vars=expansion_vars)

                # If the AST is just a literal, check if it is formatted specially.
                # This preserves formatting like underscores in version numbers (e.g. 1_01)
                # and keeps hex formatting (e.g. 0x10) for numbers.
                if isinstance(body, (_AST_CONSTANT, _AST_NUM)) and isinstance(
                    out_str, (int, float)
                ):
                    source = _get_source_segment(in_str, body)
                    if source and str(out_str) != source:
                        return source

                return out_str
            except MathEvaluationError as e:
                logger.debug(f'   Math input is: "{in_str}"')
                logger.debug(e)
            except RambleSyntaxError as e:
                raise RambleSyntaxError(f'{str(e)} in "{in_str}"') from None
            except SyntaxError as e:
                logger.debug(f"ast.parse hit the following syntax error on input: {in_str}")
                logger.debug(e)

            return in_str
        finally:
            self._math_str_stack.pop()

    def eval_math(self, node, expansion_vars=None):
        """Evaluate math from parsing the AST

        Does not assume a specific type of operands.
        Some operators will generate floating point, while
        others will generate integers (if the inputs are integers).
        """
        try:
            if hasattr(ast, "Constant") and isinstance(node, ast.Constant):
                return self._ast_constant(node)
            elif _is_name_constant_node(node):  # pragma: no cover
                return self._ast_constant(node)
            elif _is_num_node(node):
                return self._ast_num(node)
            elif isinstance(node, ast.Name):
                return self._ast_name(node)
            elif _is_str_node(node):
                return node.s
            elif isinstance(node, ast.Attribute):
                return self._ast_attr(node)
            elif isinstance(node, ast.Compare):
                return self._eval_comparisons(node, expansion_vars=expansion_vars)
            elif isinstance(node, ast.BoolOp):
                return self._eval_bool_op(node, expansion_vars=expansion_vars)
            elif isinstance(node, ast.BinOp):
                return self._eval_binary_ops(node, expansion_vars=expansion_vars)
            elif isinstance(node, ast.UnaryOp):
                return self._eval_unary_ops(node, expansion_vars=expansion_vars)
            elif isinstance(node, ast.Call):
                return self._eval_function_call(node, expansion_vars=expansion_vars)
            elif isinstance(node, ast.Subscript):
                return self._eval_subscript_op(node, expansion_vars=expansion_vars)
            else:
                node_type = str(type(node))
                raise MathEvaluationError(
                    f"Unsupported math AST node {node_type}:\n" + f"\t{node.__dict__}"
                )
        except SyntaxError as e:
            logger.debug(str(e))
            raise e

    # Ast logic helper methods
    def __raise_syntax_error(self, node):
        node_type = str(type(node))
        raise RambleSyntaxError(
            f"Syntax error while processing {node_type} node:\n" + f"{node.__dict__}"
        )

    def __dbg_syntax_error(self, msg, node):
        node_type = str(type(node))
        raise SyntaxError(
            self._ast_dbg_prefix
            + f" {msg}\n"
            + f"Occurred while processing {node_type} node:\n"
            + f"{node.__dict__}"
        )

    def _ast_num(self, node):
        """Handle a number node in the ast"""
        return node.n

    def _ast_constant(self, node):
        """Handle a constant node in the ast"""
        return node.value

    def _ast_name(self, node):
        """Handle a name node in the ast"""
        return node.id

    def _ast_attr(self, node):
        """Handle an attribute node in the ast"""
        if isinstance(node.value, ast.Attribute):
            base = self._ast_attr(node.value)
        elif isinstance(node.value, ast.Name):
            base = self._ast_name(node.value)
        else:
            self.__dbg_syntax_error(
                " Unknown attribute syntax used.\nreturning unexpanded string", node
            )

        val = f"{base}.{node.attr}"
        return val

    def _eval_function_call(self, node, expansion_vars=None):
        """Handle a subset of function call nodes in the ast"""

        kwargs = {}
        args = [self.eval_math(arg, expansion_vars=expansion_vars) for arg in node.args]
        for kw in node.keywords:
            kwargs[self.eval_math(kw.arg, expansion_vars=expansion_vars)] = self.eval_math(
                kw.value, expansion_vars=expansion_vars
            )

        if node.func.id in supported_scalar_function_pointers:
            func = supported_scalar_function_pointers[node.func.id]
            return func(*args, **kwargs)
        elif node.func.id in supported_list_function_pointers:
            func = supported_list_function_pointers[node.func.id]
            return list(func(*args, **kwargs))
        elif node.func.id in supported_scalar_function_with_self_arg_pointers:
            func = supported_scalar_function_with_self_arg_pointers[node.func.id]
            return func(self, *args, **kwargs)
        else:
            parts = node.func.id.split("_", 1)
            if len(parts) == 2:
                module_name, func_name = parts
                # Special handling for function calls prefixed with `str_`
                if module_name == "str" and len(args) > 0:
                    s = str(args[0])
                    if hasattr(s, func_name) and callable(getattr(s, func_name)):
                        s_method = getattr(s, func_name)
                        return s_method(*args[1:], **kwargs)
                elif module_name in supported_modules:
                    module = supported_modules[module_name]
                    if hasattr(module, func_name):
                        func = getattr(module, func_name)
                        return func(*args, **kwargs)

            raise MathEvaluationError(
                f"Undefined function {node.func.id} used.\n" "returning unexapanded string"
            )

    def _eval_bool_op(self, node, expansion_vars=None):
        """Handle a boolean operator node in the ast"""
        try:
            op = supported_math_operators[type(node.op)]

            result = self.eval_math(node.values[0], expansion_vars=expansion_vars)

            for value in itertools.islice(node.values, 1, None):
                result = op(result, self.eval_math(value, expansion_vars=expansion_vars))

            return result

        except TypeError:
            self.__dbg_syntax_error("Unsupported operand type in boolean operator", node)
        except KeyError:
            self.__dbg_syntax_error("Unsupported boolean operator", node)

    def _eval_comparisons(self, node, expansion_vars=None):
        """Handle a comparison node in the ast"""

        # Extract In or NotIn nodes, and call their helper
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            is_in = self._eval_comp_in(node, expansion_vars=expansion_vars)
            if isinstance(node.ops[0], ast.NotIn):
                return not is_in
            return is_in

        if len(node.ops) == 1 and isinstance(node.ops[0], ast.Is):
            raise RambleSyntaxError("Encountered unsupported operator `is`")

        # Try to evaluate the comparison logic, if not return the node as is.
        try:
            cur_left = self.eval_math(node.left, expansion_vars=expansion_vars)

            op = supported_math_operators[type(node.ops[0])]
            cur_right = self.eval_math(node.comparators[0], expansion_vars=expansion_vars)

            result = op(cur_left, cur_right)

            if len(node.ops) > 1:
                cur_left = cur_right
                for comp, right in itertools.islice(zip(node.ops, node.comparators), 1, None):
                    op = supported_math_operators[type(comp)]
                    cur_right = self.eval_math(right, expansion_vars=expansion_vars)

                    result = result and op(cur_left, cur_right)

                    cur_left = cur_right
            return result
        except TypeError:
            self.__dbg_syntax_error("Unsupported operand type in binary comparison operator", node)
        except KeyError:
            self.__dbg_syntax_error("Unsupported binary comparison operator", node)

    def _eval_comp_in(self, node, expansion_vars=None):
        """Handle in node in the ast

        Perform extraction of `<variable> in <experiment>` syntax.
        Raises an exception if the experiment does not exist.

        Also, evaluated `<value> in [list, of, values]` and `<value> in "str"` syntaxes.
        """
        if isinstance(node.left, ast.Name):
            var_name = self._ast_name(node.left)
            if isinstance(node.comparators[0], ast.Attribute):
                namespace = self.eval_math(node.comparators[0], expansion_vars=expansion_vars)
                val = self._experiment_set.get_var_from_experiment(
                    namespace, self.expansion_str(var_name)
                )
                if not val:
                    raise RambleSyntaxError(
                        f"{namespace} does not exist in: " + f'"{var_name} in {namespace}"'
                    )
                return val
        # TODO: Remove `or` logic after 3.6 & 3.7 series python are unsupported
        elif isinstance(node.left, (_AST_CONSTANT, _AST_NAME_CONSTANT)) or _is_str_node(node.left):
            lhs_value = self.eval_math(node.left, expansion_vars=expansion_vars)

            found = False
            for comp in node.comparators:
                if isinstance(comp, (ast.List, ast.Set)):
                    for elt in comp.elts:
                        rhs_value = self.eval_math(elt, expansion_vars=expansion_vars)
                        if lhs_value == rhs_value:
                            found = True
                elif isinstance(comp, (_AST_CONSTANT, _AST_NAME_CONSTANT)) or _is_str_node(comp):
                    # Attempt evaluating `"str" in "string"`
                    rhs_value = self.eval_math(comp, expansion_vars=expansion_vars)
                    if isinstance(rhs_value, str) and lhs_value in rhs_value:
                        found = True
            return found

        self.__raise_syntax_error(node)

    def _eval_binary_ops(self, node, expansion_vars=None):
        """Evaluate binary operators in the ast

        Extract the binary operator, and evaluate it.
        """
        try:
            left_eval = self.eval_math(node.left, expansion_vars=expansion_vars)
            right_eval = self.eval_math(node.right, expansion_vars=expansion_vars)
            op = supported_math_operators[type(node.op)]
            if isinstance(left_eval, str) or isinstance(right_eval, str):
                # Determine the end of the left node and the start of the right node,
                # to preserve strings in between.
                # This is to avoid expanding "gromacs +debug" into "gromacs+debug".
                op_str = None
                if self._math_str_stack:
                    source = self._math_str_stack[-1]
                    l_node, r_node = node.left, node.right

                    l_end_lineno = getattr(l_node, "end_lineno", None)
                    l_end_col_offset = getattr(l_node, "end_col_offset", None)

                    # The `end_lineno` and `end_col_offset` may not be available in older (<3.8)
                    # versions of Python.
                    if l_end_lineno is None and hasattr(l_node, "lineno"):
                        if isinstance(l_node, ast.Name):
                            l_end_lineno = l_node.lineno
                            l_end_col_offset = l_node.col_offset + len(l_node.id)
                        elif _is_num_node(l_node):
                            l_end_lineno = l_node.lineno
                            l_end_col_offset = l_node.col_offset + len(str(l_node.n))

                    if l_end_lineno is not None and hasattr(r_node, "lineno"):
                        if l_end_lineno == r_node.lineno:
                            lines = source.splitlines(keepends=True)
                            line = lines[l_end_lineno - 1]
                            op_str = line[l_end_col_offset : r_node.col_offset]
                    if op_str is not None:
                        left_eval = _get_source_segment(source, l_node) or left_eval
                        right_eval = _get_source_segment(source, r_node) or right_eval
                        return f"{left_eval}{op_str}{right_eval}"
                self.__dbg_syntax_error("Unsupported operand type in binary operator", node)
            return op(left_eval, right_eval)
        except TypeError:
            self.__dbg_syntax_error("Unsupported operand type in binary operator", node)
        except KeyError:
            self.__dbg_syntax_error("Unsupported binary operator", node)

    def _eval_unary_ops(self, node, expansion_vars=None):
        """Evaluate unary operators in the ast

        Extract the unary operator, and evaluate it.
        """
        try:
            operand = self.eval_math(node.operand, expansion_vars=expansion_vars)
            if isinstance(operand, str):
                self.__dbg_syntax_error("Unsupported operand type in unary operator", node)
            op = supported_math_operators[type(node.op)]
            return op(operand)
        except TypeError:
            self.__dbg_syntax_error("Unsupported operand type in unary operator", node)
        except KeyError:
            self.__dbg_syntax_error("Unsupported unary operator", node)

    def _eval_subscript_op(self, node, expansion_vars=None):
        """Evaluate subscript operation in the ast"""
        try:
            operand = self.eval_math(node.value, expansion_vars=expansion_vars)
            slice_node = node.slice

            active_vars = expansion_vars if expansion_vars is not None else self._variables

            if isinstance(operand, str):
                if isinstance(slice_node, ast.Slice):

                    def _get_with_default(s_node, attr, default):
                        v_node = getattr(s_node, attr)
                        if v_node is None:
                            return default
                        return self.eval_math(v_node, expansion_vars=expansion_vars)

                    lower = _get_with_default(slice_node, "lower", 0)
                    upper = _get_with_default(slice_node, "upper", len(operand))
                    step = _get_with_default(slice_node, "step", 1)
                    return operand[slice(lower, upper, step)]
                elif operand in active_vars and isinstance(active_vars[operand], dict):
                    op_dict = self.expand_var_name(operand, extra_vars=active_vars, typed=True)

                    if _is_index_node(slice_node):
                        key = self.eval_math(slice_node.value, expansion_vars=active_vars)
                    elif isinstance(
                        slice_node, (_AST_CONSTANT, _AST_NAME_CONSTANT)
                    ) or _is_str_node(slice_node):
                        key = self.eval_math(slice_node, expansion_vars=active_vars)
                    else:
                        key = None

                    if key is None:
                        msg = (
                            "During dictionary extraction, key is None. " + "Skipping extraction."
                        )
                        self.__dbg_syntax_error(msg, node)

                    if key not in op_dict:
                        msg = (
                            f"Key {key} is not in dictionary {operand}. " + "Cannot extract value."
                        )
                        self.__dbg_syntax_error(msg, node)

                    return op_dict[key]

            msg = (
                "Currently subscripts are only support "
                + "for string slicing, and key extraction from dictionaries"
            )
            self.__dbg_syntax_error(msg, node)
        except TypeError:
            msg = "Unsupported operand type in subscript operator"
            self.__dbg_syntax_error(msg, node)


def raise_passthrough_error(in_str, out_str):
    """Raise an error when passthrough is disabled but variables are not all expanded"""

    logger.debug(f"Expansion stack errors: attempted to expand " f'"{in_str}"')
    logger.debug(f"  As: {out_str}")
    raise RamblePassthroughError("Error Stack:\n" f'Input: "{in_str}"\n' f'Output: "{out_str}"\n')


class ExpanderError(ramble.error.RambleError):
    """Raised when an error happens within an expander"""


class MathEvaluationError(ExpanderError):
    """Raised when an error happens while evaluating math during
    expansion
    """


class RambleSyntaxError(ExpanderError):
    """Raised when a syntax error happens within variable definitions"""


class RamblePassthroughError(ExpanderError):
    """Raised when passthrough is disabled and variables fail to expand"""


class WorkloadNotDefinedError(ExpanderError):
    """Raised when a workload is not defined properly"""
