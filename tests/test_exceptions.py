import importlib
import pkgutil
from collections.abc import Iterator

import jyyfinhub_spendtracker
from jyyfinhub_spendtracker.core.exceptions import SpendTrackerError


def _import_every_exceptions_module() -> None:
    """__subclasses__ only sees imported classes, so pull in every feature's exceptions.py"""
    for module in pkgutil.walk_packages(
        jyyfinhub_spendtracker.__path__, prefix="jyyfinhub_spendtracker."
    ):
        if module.name.endswith(".exceptions"):
            importlib.import_module(module.name)


def _descendants(cls: type) -> Iterator[type]:
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _descendants(subclass)


def test_error_codes_are_unique() -> None:
    """error_code is part of the API contract, and feature modules cannot see each other's"""
    _import_every_exceptions_module()

    codes = [c.error_code for c in _descendants(SpendTrackerError)]

    assert codes, "no exception subclasses found, so this test proves nothing"
    duplicates = {code for code in codes if codes.count(code) > 1}
    assert not duplicates, f"duplicate error_code: {sorted(duplicates)}"
