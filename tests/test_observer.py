from pathlib import Path

from runnerlens import observer
from runnerlens.observer import parse_strace_execve


def test_parse_strace_execve_keeps_successful_process_tree_events() -> None:
    trace = '''execve("/usr/bin/make", ["make"], 0x0 /* 1 var */) = 0
[pid 42] execve("/usr/bin/cmake", ["cmake"], 0x0 /* 1 var */) = 0
[pid 42] execve("/usr/bin/missing", ["missing"], 0x0 /* 1 var */) = -1 ENOENT (No such file or directory)
'''

    events = parse_strace_execve(trace)

    assert [(event.executable, event.path, event.pid) for event in events] == [
        ("make", "/usr/bin/make", None),
        ("cmake", "/usr/bin/cmake", 42),
    ]
    assert all(event.observation == "strace-execve" for event in events)


def test_parse_strace_execve_decodes_escaped_paths() -> None:
    events = parse_strace_execve('execve("/work/my\\040tool", [], 0x0) = 0\n')

    assert events[0].path == "/work/my tool"
    assert events[0].executable == "my tool"


def test_observer_retains_root_event_when_strace_has_no_parseable_events(monkeypatch) -> None:
    monkeypatch.setattr(observer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(observer.shutil, "which", lambda executable, path=None: "/usr/bin/" + executable)
    monkeypatch.setattr(observer, "_observe_with_strace", lambda argv, cwd: ([], 0))

    result = observer.observe_command(["bash"])

    assert len(result.events) == 1
    assert result.events[0].path == "/usr/bin/bash"
    assert result.events[0].observation == "subprocess-root-fallback"
