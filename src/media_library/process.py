"""Subprocesos sin shell, con diagnóstico y terminación del grupo en fallos."""

from dataclasses import dataclass
import os
import signal
import subprocess


class ToolError(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__(f"{result.args[0]}: {result.error or result.stderr or result.returncode}")


@dataclass(frozen=True)
class ProcessResult:
    args: tuple[str, ...]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    timed_out: bool = False

    @property
    def ok(self):
        return self.returncode == 0 and not self.error and not self.timed_out

    def check(self):
        if not self.ok:
            raise ToolError(self)
        return self


def run_tool(args, *, timeout=60, cwd=None):
    if isinstance(args, (str, bytes)) or not args or timeout <= 0:
        raise ValueError("Se requiere lista de argumentos y timeout positivo")
    args = tuple(os.fspath(arg) for arg in args)
    try:
        process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, errors="replace", start_new_session=True)
    except OSError as exc:
        return ProcessResult(args, None, error=str(exc))
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        if isinstance(exc, KeyboardInterrupt):
            raise
        return ProcessResult(args, process.returncode, stdout, stderr, "timeout", True)
    return ProcessResult(args, process.returncode, stdout, stderr)
