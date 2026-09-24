# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.language.language_helpers
from ramble.language.shared_language import edit_file


class MockApp:
    def __init__(self):
        self.name = "mock_app"
        self.origin_type = "application"
        self.executables = {}
        self.custom_edit_functions = {}


@pytest.fixture
def mock_app():
    return MockApp()


def test_edit_file_valid_function(mock_app):
    def my_custom_edit(content):
        return content.replace("a", "b")

    # The directive is usually used as a decorator on the class,
    # but here we call the returned function directly.
    edit_func = edit_file("my_edit", "/path/f", function=my_custom_edit)
    edit_func(mock_app)

    assert "my_edit" in mock_app.custom_edit_functions
    source = mock_app.custom_edit_functions["my_edit"]
    assert "def custom_edit_my_edit_my_custom_edit(content):" in source
    assert "return my_custom_edit(content)" in source

    template = mock_app.executables[frozenset()]["my_edit"].template[0]
    assert "--function custom_edit_my_edit_my_custom_edit" in template


def test_edit_file_invalid_lambda(mock_app):
    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="Directive 'my_edit' in application 'mock_app' requires a named top-level "
        "function, not a lambda or a method",
    ):
        edit_func = edit_file("my_edit", "/path/f", function=lambda c: c)
        edit_func(mock_app)


def test_edit_file_invalid_method(mock_app):
    class SomeClass:
        def my_method(self, content):
            return content

    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="Directive 'my_edit' in application 'mock_app' requires a named top-level "
        "function, not a lambda or a method",
    ):
        edit_func = edit_file("my_edit", "/path/f", function=SomeClass().my_method)
        edit_func(mock_app)


def test_edit_file_invalid_signature(mock_app):
    def too_many_args(content, extra):
        return content

    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="Directive 'my_edit' in application 'mock_app' requires a function that "
        "accepts exactly one argument",
    ):
        edit_func = edit_file("my_edit", "/path/f", function=too_many_args)
        edit_func(mock_app)


def test_edit_file_missing_return(mock_app):
    def no_return(content):
        print(content)

    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="Directive 'my_edit' in application 'mock_app' requires the function "
        "'no_return' to return a value",
    ):
        edit_func = edit_file("my_edit", "/path/f", function=no_return)
        edit_func(mock_app)


def test_edit_file_collision_avoidance(mock_app):
    def edit(content):
        return content + "1"

    def another_edit(content):
        return content + "2"

    edit_func1 = edit_file("e1", "/path/f1", function=edit)
    edit_func1(mock_app)

    edit_func2 = edit_file("e2", "/path/f2", function=another_edit)
    edit_func2(mock_app)

    assert "e1" in mock_app.custom_edit_functions
    assert "e2" in mock_app.custom_edit_functions

    source1 = mock_app.custom_edit_functions["e1"]
    source2 = mock_app.custom_edit_functions["e2"]

    assert "def custom_edit_e1_edit(content):" in source1
    assert "def custom_edit_e2_another_edit(content):" in source2

    template1 = mock_app.executables[frozenset()]["e1"].template[0]
    template2 = mock_app.executables[frozenset()]["e2"].template[0]

    assert "--function custom_edit_e1_edit" in template1
    assert "--function custom_edit_e2_another_edit" in template2


def test_write_utilities(tmpdir):
    import os

    from ramble.workspace import workspace

    ws_root = str(tmpdir.mkdir("ws"))
    ws = workspace.Workspace(ws_root, True)

    ws.write_utilities()

    shared_util_dir = os.path.join(ws_root, "shared", "utilities")
    assert os.path.exists(shared_util_dir)

    # Base script
    assert os.path.exists(os.path.join(shared_util_dir, "_ramble_file_editor.py"))


def test_edit_file_missing_replace(mock_app):
    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="requires both 'match' and 'replace' to be specified together",
    ):
        edit_func = edit_file("my_edit", "/path/f", match="foo")
        edit_func(mock_app)


def test_edit_file_missing_match(mock_app):
    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="requires both 'match' and 'replace' to be specified together",
    ):
        edit_func = edit_file("my_edit", "/path/f", replace="foo")
        edit_func(mock_app)


def test_edit_file_no_actions(mock_app):
    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="requires at least one action \\(match/replace, append, "
        "prepend, or function\\) to be specified",
    ):
        edit_func = edit_file("my_edit", "/path/f")
        edit_func(mock_app)


def test_edit_file_unretrievable_source(mock_app):
    # Dynamically created function has no source code file
    d = {}
    exec("def dynamic_func(content):\n    return content", d)
    dynamic_func = d["dynamic_func"]

    with pytest.raises(
        ramble.language.language_helpers.DirectiveError,
        match="could not retrieve source for function",
    ):
        edit_func = edit_file("my_edit", "/path/f", function=dynamic_func)
        edit_func(mock_app)


def test_patch_file_directive():
    from ramble.language.shared_language import patch_file

    # Create an app without executables to cover that branch
    class EmptyApp:
        def __init__(self):
            self.name = "empty_app"

    app = EmptyApp()
    patch_func = patch_file("my_patch", "/path/f", "/path/to/patch")
    patch_func(app)

    # Adding a second one to hit the line where executables dict exists
    patch_func2 = patch_file("my_patch2", "/path/f2", "/path/to/patch2")
    patch_func2(app)

    when_set = frozenset()
    assert "my_patch" in app.executables[when_set]
    assert "my_patch2" in app.executables[when_set]
    template = app.executables[when_set]["my_patch"].template[0]
    assert "--mode patch" in template


def test_edit_file_directive_empty_app():
    # Same for edit_file
    class EmptyApp:
        def __init__(self):
            self.name = "empty_app"
            self.custom_edit_functions = {}

    app = EmptyApp()
    edit_func = edit_file("my_edit", "/path/f", match="a", replace="b")
    edit_func(app)
    assert "my_edit" in app.executables[frozenset()]


@pytest.fixture
def editor_script_path(tmpdir):
    from ramble.util.file_editor import get_file_editor_script

    script_path = tmpdir.join("test_file_editor.py")
    script_path.write(get_file_editor_script())
    return str(script_path)


@pytest.fixture
def run_editor(editor_script_path):
    import subprocess
    import sys

    def _run(*args):
        return subprocess.run(
            [sys.executable, editor_script_path] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )

    return _run


def test_editor_script_regex_basic(tmpdir, run_editor):
    # Create a test file
    test_file = tmpdir.join("test.txt")
    test_file.write("hello world\nthis is a test\n")

    # Run the editor script to replace "world" with "ramble"
    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--match",
        "world",
        "--replace",
        "ramble",
    )

    assert res.returncode == 0
    assert test_file.read() == "hello ramble\nthis is a test\n"


def test_editor_script_regex_append_prepend(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("content\n")

    # Run editor script with append and prepend
    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--append",
        "\\nfooter\\n",
        "--prepend",
        "header\\n\\n",
    )

    assert res.returncode == 0
    assert test_file.read() == "header\n\ncontent\n\nfooter\n"


def test_editor_script_custom_function(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("original content")

    # Create a custom module with an edit function
    module_file = tmpdir.join("custom_funcs.py")
    module_file.write(
        "def my_edit(content):\n" "    return content.replace('original', 'modified')\n"
    )

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--import-module",
        str(module_file),
        "--function",
        "my_edit",
    )

    assert res.returncode == 0
    assert test_file.read() == "modified content"


def test_editor_script_custom_function_invalid_return(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("content")

    module_file = tmpdir.join("custom_funcs.py")
    module_file.write("def invalid_edit(content):\n" "    return 123\n")

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--import-module",
        str(module_file),
        "--function",
        "invalid_edit",
    )

    assert res.returncode == 1
    assert "must return a string, not int" in (res.stdout + res.stderr)


def test_editor_script_custom_function_not_found(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("content")

    module_file = tmpdir.join("custom_funcs.py")
    module_file.write("def valid_edit(content):\n" "    return content\n")

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--import-module",
        str(module_file),
        "--function",
        "missing_edit",
    )

    assert res.returncode == 1
    assert "Function missing_edit not found" in (res.stdout + res.stderr)


def test_editor_script_module_not_found(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("content")

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--import-module",
        str(tmpdir.join("non_existent_module.py")),
        "--function",
        "my_edit",
    )

    assert res.returncode == 1
    output = res.stdout + res.stderr
    assert "Module file" in output
    assert "not found" in output


def test_editor_script_patch_success(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("line 1\nline 2\nline 3\n")

    patch_file = tmpdir.join("test.patch")
    patch_file.write(
        "--- test.txt\n"
        "+++ test.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )

    res = run_editor(
        "--mode",
        "patch",
        "--file",
        str(test_file),
        "--patch-file",
        str(patch_file),
    )

    assert res.returncode == 0
    assert "line 2 modified" in test_file.read()


def test_editor_script_patch_failure(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("line 1\nline 2\nline 3\n")

    # Invalid patch file contents
    patch_file = tmpdir.join("test.patch")
    patch_file.write("invalid patch contents\n")

    res = run_editor(
        "--mode",
        "patch",
        "--file",
        str(test_file),
        "--patch-file",
        str(patch_file),
    )

    assert res.returncode == 1
    assert "Error applying patch" in (res.stdout + res.stderr)


def test_editor_script_preserves_line_endings(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write_binary(b"line1\r\nline2\r\n")

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--match",
        "line1",
        "--replace",
        "modified1",
    )

    assert res.returncode == 0
    content = test_file.read_binary()
    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert content == b"modified1\r\nline2\r\n"


def test_editor_script_create_directory(tmpdir, run_editor):
    import os

    nested_dir = os.path.join(str(tmpdir), "new_sub_dir")
    test_file = os.path.join(nested_dir, "test.txt")

    assert not os.path.exists(nested_dir)

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        test_file,
        "--prepend",
        "new file content",
    )

    assert res.returncode == 0
    assert os.path.exists(test_file)
    with open(test_file, encoding="utf-8") as f:
        assert f.read() == "new file content"


def test_editor_script_no_unnecessary_write(tmpdir, run_editor):
    import os
    import time

    test_file = tmpdir.join("test.txt")
    test_file.write("hello world")

    # Set mtime back in the past
    past_time = time.time() - 3600
    os.utime(str(test_file), (past_time, past_time))

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--match",
        "not_present",
        "--replace",
        "something",
    )

    assert res.returncode == 0
    # The file mtime should remain unchanged
    assert os.path.getmtime(str(test_file)) == pytest.approx(past_time, abs=1)


def test_editor_script_globals_function_not_found(tmpdir, run_editor):
    test_file = tmpdir.join("test.txt")
    test_file.write("content")

    res = run_editor(
        "--mode",
        "regex",
        "--file",
        str(test_file),
        "--function",
        "my_edit",
    )

    assert res.returncode == 1
    assert "Function my_edit not found" in (res.stdout + res.stderr)
