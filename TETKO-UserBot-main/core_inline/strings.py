# SPDX-License-Identifier: MIT
# Copyright (c) 2026 flexownerAL | @flexownerAL

from utils.strings import Strings


def get_strings(kernel) -> Strings:
    return Strings(kernel, {"name": "core_inline"})
