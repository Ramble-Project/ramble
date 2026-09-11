# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


def define_directive_methods_on_class(cls):
    """Create methods that execute directives on the class.

    Wrap each directive, and inject it into this class as a method.
    """
    if not hasattr(cls, "_directive_functions"):
        return

    lang_types = set(getattr(cls, "_language_types", [])) | set(
        getattr(cls, "_language_classes", [])
    )
    directive_types = getattr(cls, "_directive_types", {})
    directive_classes = getattr(cls, "_directive_classes", {})

    for directive in cls._directive_functions:
        d_type = directive_types.get(directive)
        d_cls = directive_classes.get(directive)
        if (d_type in lang_types or d_cls in lang_types) and not hasattr(cls, directive):
            setattr(cls, directive, wrap_named_directive_class_level(directive))


def wrap_named_directive_class_level(name):
    """Wrap a directive to simplify execution at the class level

    Create a bound-like method that executes a directive on the instance
    """

    def _execute_directive(self, *args, directive_name=name, **kwargs):
        import ramble.language.language_base

        ramble.language.language_base.DirectiveMeta._executing_directives_depth += 1
        try:
            self._directive_functions[directive_name](*args, **kwargs)(self)
        finally:
            ramble.language.language_base.DirectiveMeta._executing_directives_depth -= 1

    return _execute_directive
