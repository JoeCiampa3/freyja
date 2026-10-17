"""
Open a node file in an editor. Resolution order: FREYJA_EDITOR (a command containing {path}); VISUAL, then EDITOR; `code -g` when `code`
is on the PATH; the operating system's file association (os.startfile).

Launching: the command is resolved to a full path with shutil.which first. On Windows `code` is code.CMD, and CreateProcess applies no
PATHEXT to a bare name, so Popen(["code"]) raised WinError 2 (memo 14, finding 5). A .cmd or .bat shim is run through cmd.exe. If the
launch fails the file association is tried; if that fails too, EditorError carries both causes.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

# Characters cmd.exe reinterprets inside a quoted argument (% expands variables, ^ and ! escape or expand); such a path never goes through it.
CMD_UNSAFE = set('%^!"' + chr(13) + chr(10) + chr(0))


class EditorError(OSError):
    """The editor could not be launched by any route."""


def _split(cmd: str) -> list:
    """Split a command line. On Windows backslashes are path separators, so quotes are honoured but escapes are not."""
    if os.name == "nt":
        return [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in shlex.split(cmd, posix=False)]
    return shlex.split(cmd)


def resolve(env, path: str, which=None) -> list:
    """The argv to run; ["startfile", path] stands for os.startfile."""
    which = which or __import__("shutil").which
    custom = env.get("FREYJA_EDITOR")
    if custom and "{path}" in custom:
        return [part.replace("{path}", path) for part in _split(custom)]
    for var in ("VISUAL", "EDITOR"):
        if env.get(var):
            return [*_split(env[var]), path]
    if which("code"):
        return ["code", "-g", path]
    return ["startfile", path]


def node_file(root, rel) -> Path:
    """The node file as an absolute path, which must lie under the root."""
    base = Path(root).resolve()
    p = (base / rel).resolve()
    if base != p and base not in p.parents:
        raise ValueError(f"{rel} is outside {root}")
    return p


def _launch(argv, which, popen, windows):
    """Start argv. Returns nothing; raises OSError. A .cmd/.bat shim on Windows goes through cmd.exe as one quoted command line."""
    exe = which(argv[0]) or argv[0]
    args = [exe, *argv[1:]]
    if windows and exe.lower().endswith((".cmd", ".bat")):
        if any(c in CMD_UNSAFE for a in args for c in a):
            raise OSError("an argument contains a character cmd.exe would reinterpret")
        line = subprocess.list2cmdline(args)
        popen(f'"{os.environ.get("COMSPEC", "cmd.exe")}" /d /s /c "{line}"')
    else:
        popen(args)
    return args


def open_file(path, env=None, which=None, popen=None, startfile=None, windows=None) -> list:
    which = which or shutil.which
    windows = os.name == "nt" if windows is None else windows
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    popen = popen or (lambda a: subprocess.Popen(a, **quiet))
    startfile = startfile or getattr(os, "startfile", None) or (lambda p: subprocess.Popen(["xdg-open", p], **quiet))
    argv = resolve(os.environ if env is None else env, str(path), which)
    first = None
    if argv[0] != "startfile":
        try:
            return _launch(argv, which, popen, windows)
        except OSError as e:
            first = e
    try:
        startfile(str(path))
    except OSError as e2:
        raise EditorError(f"could not open {path}: {first or 'no editor configured'}; file association: {e2}") from e2
    return ["startfile", str(path)]
