# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools
from typing import Optional


@functools.lru_cache(maxsize=None)
def _parse_spec_string(spec_like):
    if not spec_like:
        return "", None, None

    # Strip any version suffix if present (e.g., app@1.0)
    spec_like = spec_like.partition("@")[0].lower()

    parts = spec_like.split(".")

    import ramble.repository

    type_map = ramble.repository.get_object_type_map()

    if len(parts) >= 3 and parts[-2] in type_map:
        object_type = type_map[parts[-2]]
        name = parts[-1]
        namespace = ".".join(parts[:-2])
    elif len(parts) >= 2:
        if len(parts) == 2 and parts[0] in type_map:
            object_type = type_map[parts[0]]
            name = parts[1]
            namespace = None
        else:
            object_type = None
            name = parts[-1]
            namespace = ".".join(parts[:-1])
    else:
        object_type = None
        name = parts[0]
        namespace = None

    return name, namespace, object_type


class Spec:
    def __init__(self, spec_like=None, object_type=None):
        """Create a new Spec.

        Arguments:
            spec_like (optional string or Spec): If not provided we initialize an
                anonymous Spec that matches any Spec object; if provided we parse
                this as a Spec string.
            object_type (optional ObjectTypes): Optional object type enum.
        """
        # Copy if spec_like is a Spec.
        if isinstance(spec_like, Spec):
            self.name: Optional[str] = spec_like.name
            self.namespace: Optional[str] = spec_like.namespace
            self.object_type = object_type if object_type is not None else spec_like.object_type
            return

        # init an empty spec that matches anything.
        self.name: Optional[str] = None
        self.namespace: Optional[str] = None
        self.object_type = object_type

        if isinstance(spec_like, str):
            self.name, self.namespace, parsed_type = _parse_spec_string(spec_like)
            if self.object_type is None:
                self.object_type = parsed_type

    def copy(self) -> "Spec":
        return Spec(self)

    def __str__(self) -> str:
        return self.name if self.name is not None else ""

    def __repr__(self) -> str:
        return (
            f"Spec(name={self.name!r}, namespace={self.namespace!r}, "
            f"object_type={self.object_type!r})"
        )

    def __eq__(self, other) -> bool:
        if isinstance(other, Spec):
            return (
                self.name == other.name
                and self.namespace == other.namespace
                and self.object_type == other.object_type
            )
        return False

    def __hash__(self) -> int:
        return hash((self.name, self.namespace, self.object_type))

    @property
    def fullname(self) -> str:
        if not self.name:
            return ""
        import ramble.repository

        if self.namespace:
            if self.object_type:
                abbrev = ramble.repository.type_definitions[self.object_type]["abbrev"]
                return f"{self.namespace}.{abbrev}.{self.name}"
            return f"{self.namespace}.{self.name}"
        else:
            if self.object_type:
                abbrev = ramble.repository.type_definitions[self.object_type]["abbrev"]
                return f"{abbrev}.{self.name}"
            return self.name
