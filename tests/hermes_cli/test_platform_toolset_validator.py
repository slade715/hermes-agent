"""Tests for the ``platform_toolsets`` validity predicate used by config migration.

``hermes_cli.toolset_validation`` deliberately takes the validity predicate as an argument ("no
registry imports or I/O"), so plugin awareness lives at the call site. This covers that call site:
a plugin toolset is registered by its plugin at load time under the manifest name with ``-``
normalised to ``_``, and ``toolsets.validate_toolset`` — which only knows the core ``TOOLSETS``
map — reports it as unknown, making the platform look like it has no tools.
"""

import hermes_cli.config as config_mod
import hermes_cli.plugins as plugins_mod
from hermes_cli.config import _platform_toolset_validator


def test_core_toolsets_are_valid_without_any_plugin():
    is_valid = _platform_toolset_validator()
    assert is_valid("terminal")
    assert is_valid("hermes-cli")
    assert not is_valid("definitely_not_a_toolset")


def test_plugin_toolset_keys_are_valid(monkeypatch):
    """A plugin toolset must not be reported unknown.

    Pinned by monkeypatch rather than by whatever happens to be installed, so this holds in CI
    (where no user plugins exist) exactly as it does on a developer machine.
    """
    monkeypatch.setattr(
        plugins_mod, "get_plugin_toolset_keys_nowait", lambda: {"handflow", "jev_tools"},
        raising=False)

    is_valid = _platform_toolset_validator()
    assert is_valid("handflow")
    assert is_valid("jev_tools")
    # Core toolsets keep working through the same predicate.
    assert is_valid("terminal")
    assert not is_valid("nope_not_a_toolset")


def test_plugin_discovery_failure_degrades_to_core_only(monkeypatch):
    """Discovery is best-effort: a broken plugin layer must not make config migration explode, and
    must not silently declare every name valid."""
    def _boom():
        raise RuntimeError("plugin discovery exploded")

    monkeypatch.setattr(plugins_mod, "get_plugin_toolset_keys_nowait", _boom, raising=False)

    is_valid = _platform_toolset_validator()
    assert is_valid("terminal")
    assert not is_valid("handflow")


def test_warning_path_reports_nothing_for_plugin_toolsets(monkeypatch):
    """End-to-end through the warning collector: the shape a real install hit
    (``cli: [..., handflow, jev_tools, ...]``) must produce no warning at all while the
    underlying core check still rejects those names — which is precisely the false positive."""
    from toolsets import validate_toolset

    monkeypatch.setattr(
        plugins_mod, "get_plugin_toolset_keys_nowait", lambda: {"handflow", "jev_tools"},
        raising=False)
    monkeypatch.setattr(
        config_mod, "read_raw_config",
        lambda: {"platform_toolsets": {"cli": ["terminal", "handflow", "jev_tools"]}},
        raising=False)

    # The premise of the bug: the core-only check calls these unknown.
    assert not validate_toolset("handflow")
    assert not validate_toolset("jev_tools")

    results = {"warnings": []}
    config_mod._warn_invalid_platform_toolsets(results, quiet=True)
    assert results["warnings"] == []
