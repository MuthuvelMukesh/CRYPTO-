"""Automated integration test verifying all research notebooks execute cleanly."""

import glob
import json

import pytest


@pytest.mark.parametrize("notebook_path", sorted(glob.glob("notebooks/*.ipynb")))
def test_notebook_execution(notebook_path: str):
    """Assert each research notebook code cells execute without unhandled exceptions."""
    with open(notebook_path, encoding="utf-8") as f:
        nb = json.load(f)

    code_cells = [cell for cell in nb.get("cells", []) if cell.get("cell_type") == "code"]
    full_code = "\n".join("".join(cell.get("source", [])) for cell in code_cells)

    # Execute in clean global namespace
    exec_globals: dict = {"__name__": "__main__"}
    exec(full_code, exec_globals)
