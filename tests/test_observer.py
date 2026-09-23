from pathlib import Path

from runnerlens import observer
from runnerlens.observer import parse_strace_execve


def test_parse_strace_execve_keeps_successful_process_tree_events() -> None:
    trace = '''getpid() = 42
execve("/usr/bin/make", ["make"], 0x0 /* 1 var */) = 0
[pid 42] clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID) = 43
[pid 43] execve("/usr/bin/cmake", ["cmake"], 0x0 /* 1 var */) = 0
43 vfork() = 44
[pid 44] execve("/usr/bin/ninja", ["ninja"], 0x0 /* 1 var */) = 0
[pid 42] execve("/usr/bin/missing", ["missing"], 0x0 /* 1 var */) = -1 ENOENT (No such file or directory)
'''

    events = parse_strace_execve(trace)

    assert [(event.executable, event.path, event.pid, event.parent_pid) for event in events] == [
        ("make", "/usr/bin/make", None, None),
        ("cmake", "/usr/bin/cmake", 43, 42),
        ("ninja", "/usr/bin/ninja", 44, 43),
    ]
    assert all(event.observation == "strace-execve" for event in events)


def test_parse_strace_execve_decodes_escaped_paths() -> None:
    events = parse_strace_execve('execve("/work/my\\040tool", [], 0x0) = 0\n')

    assert events[0].path == "/work/my tool"
    assert events[0].executable == "my tool"


def test_parse_strace_execve_keeps_unknown_or_out_of_order_lineage_unset() -> None:
    trace = '''[pid 43] execve("/usr/bin/cmake", ["cmake"], 0x0) = 0
[pid 42] fork() = 43
clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID) = 44
[pid 44] execve("/usr/bin/ninja", ["ninja"], 0x0) = 0
'''

    events = parse_strace_execve(trace)

    assert events[0].parent_pid is None
    assert events[1].parent_pid is None


def test_parse_strace_execve_uses_reported_root_pid_for_unprefixed_fork() -> None:
    trace = '''getpid() = 42
fork() = 43
[pid 43] execve("/usr/bin/cmake", ["cmake"], 0x0) = 0
'''

    events = parse_strace_execve(trace)

    assert events[0].parent_pid == 42


def test_observer_retains_root_event_when_strace_has_no_parseable_events(monkeypatch) -> None:
    monkeypatch.setattr(observer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(observer.shutil, "which", lambda executable, path=None: "/usr/bin/" + executable)
    monkeypatch.setattr(observer, "_observe_with_strace", lambda argv, cwd: ([], 0))

    result = observer.observe_command(["bash"])

    assert len(result.events) == 1
    assert result.events[0].path == "/usr/bin/bash"
    assert result.events[0].observation == "subprocess-root-fallback"
