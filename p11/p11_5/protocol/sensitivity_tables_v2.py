"""Serialize the unchanged, frozen sensitivity diagnostics as native JSON.

The original calculations return NumPy boolean scalars for logistic crossing
range flags. This adapter changes only the writer boundary, preserving the
original diagnostic implementation and the single locked development score.
"""
import importlib
import numpy as np


def native_json(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: native_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [native_json(item) for item in value]
    return value


def run_diagnostics(module):
    original_write = module.write

    def write_native(path, value, **kwargs):
        return original_write(path, native_json(value), **kwargs)

    module.write = write_native
    try:
        return module.main()
    finally:
        module.write = original_write


def main():
    return run_diagnostics(importlib.import_module('sensitivity_tables'))


if __name__ == '__main__':
    main()
