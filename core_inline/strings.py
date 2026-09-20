# SPDX-License-Identifier: MIT

from utils.strings import Strings


def get_strings(kernel) -> Strings:
    return Strings(kernel, {"name": "core_inline"})
