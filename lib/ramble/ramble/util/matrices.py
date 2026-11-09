# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
from ramble.namespace import namespace
from ramble.util.logger import logger


def extract_matrices(action, name, in_dict):
    """Extract matrix definitions from a dictionary

    Args:
        action: The action of an object definition where
                 matrices are being extracted from
        name: The name of the object
        in_dict: The dictionary containing definitions

    Returns:
        list[Any]: List of matrix definitions
    """
    matrices = []

    if namespace.matrix in in_dict:
        matrices.append(list(in_dict[namespace.matrix]))

    if namespace.matrices in in_dict:
        for matrix in in_dict[namespace.matrices]:
            # Extract named matrices
            if isinstance(matrix, dict):
                if len(matrix.keys()) != 1:
                    logger.die(
                        f"While performing {action} with {name} "
                        " each list element may only contain "
                        "1 matrix in a matrices definition."
                    )

                matrices.extend(list(val) for val in matrix.values())
            elif isinstance(matrix, list):
                matrices.append(list(matrix))
    return matrices
