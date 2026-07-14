"""Task 0 smoke test: the package installs and the schema module imports."""

from schema.models import Category, Classification, WORecord


def test_schema_imports() -> None:
    assert Category.FAILURE.value == "failure"
    assert WORecord.__name__ == "WORecord"
    assert Classification.__name__ == "Classification"
