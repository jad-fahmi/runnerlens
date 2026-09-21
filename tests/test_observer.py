from pathlib import Path

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
