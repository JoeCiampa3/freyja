"""
Open a node file in an editor. Resolution order: FREYJA_EDITOR (a command containing {path}); VISUAL, then EDITOR; `code -g` when `code`
is on the PATH; the operating system's file association (os.startfile).
"""
from __future__ import annotations

import os
import shlex
import subprocess


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


def open_file(path, env=None, which=None, popen=None, startfile=None) -> list:
    argv = resolve(os.environ if env is None else env, str(path), which)
    if argv[0] == "startfile":
        (startfile or getattr(os, "startfile", None) or (lambda p: subprocess.Popen(["xdg-open", p])))(argv[1])
    else:
        (popen or subprocess.Popen)(argv)
    return argv
