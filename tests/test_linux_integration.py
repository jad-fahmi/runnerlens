import json
import platform
import shutil
from pathlib import Path

import pytest

from runnerlens.cli import main
from runnerlens.impact import observation_coverage
from runnerlens.observer import _can_trace_process_tree, observe_command
from runnerlens.receipt import build_receipt, load_receipt, receipt_from_dict, write_receipt
from runnerlens.resolver import find_package_owner


pytestmark = pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux")


@pytest.fixture
def tracing_available() -> None:
    if not shutil.which("strace") or not _can_trace_process_tree():
        pytest.skip("requires working strace process tracing")


def test_real_child_execution_round_trips_without_command_arguments(
    tmp_path: Path, tracing_available: None
) -> None:
    observation = observe_command(
        ["/bin/sh", "-c", "/usr/bin/true & wait", "runnerlens-private-argument"],
        cwd=tmp_path,
    )
    receipt = build_receipt(observation, repository_root=tmp_path, env={})
    output = tmp_path / "receipt.json"

    write_receipt(receipt, output)
    restored = receipt_from_dict(load_receipt(output))

    assert restored.exit_code == 0
    assert observation_coverage(restored) == "process-tree"
    assert any(event.path == "/usr/bin/true" for event in restored.events)
    assert any(dependency.path == "/usr/bin/true" for dependency in restored.dependencies)
    assert "runnerlens-private-argument" not in output.read_text(encoding="utf-8")


def test_real_json_run_separates_build_output(
    tmp_path: Path, tracing_available: None, capfd
) -> None:
    output = tmp_path / "receipt.json"

    exit_code = main(
        ["run", "--json", "--output", str(output), "--", "/bin/sh", "-c", "printf build-output"]
    )

    captured = capfd.readouterr()
    receipt = receipt_from_dict(json.loads(captured.out))
    assert exit_code == 0
    assert receipt.exit_code == 0
    assert observation_coverage(receipt) == "process-tree"
    assert "build-output" in captured.err
    assert json.loads(captured.out) == load_receipt(output)


def test_real_dpkg_query_reports_its_own_package() -> None:
    executable = shutil.which("dpkg-query")
    if executable is None:
        pytest.skip("requires Debian package database")

    owner = find_package_owner(executable)

    assert owner is not None
    assert owner.partition(":")[0] == "dpkg"
