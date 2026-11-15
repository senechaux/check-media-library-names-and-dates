"""Entrada de consola del proceso reanudable."""

import argparse
from contextlib import contextmanager
import signal
import sys
import threading

from .config import load_config, preflight
from .pipeline import Console, Pipeline
from .state import RunStore, SourceLock


@contextmanager
def interruption_signals():
    previous = {}
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    if threading.current_thread() is threading.main_thread():
        for name in ("SIGHUP", "SIGTERM"):
            if hasattr(signal, name):
                number = getattr(signal, name)
                previous[number] = signal.signal(number, interrupt)
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main(argv=None, *, console=None, adapters=None):
    parser = argparse.ArgumentParser(prog="python -m media_library")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Planificar, aplicar o reanudar etapas locales")
    run.add_argument("--config", required=True)
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    run.add_argument("--resume", metavar="RUN_ID")
    run.add_argument("--recover-stale-lock", action="store_true", help="Reconocer explícitamente un bloqueo obsoleto; nunca desplaza uno activo")
    args = parser.parse_args(argv)
    console = console or Console()
    pipeline = None
    try:
        config = load_config(args.config)
        preflight(config)
        with interruption_signals(), SourceLock(config.source, recover_stale=args.recover_stale_lock) as lock:
            store = RunStore.load(config, lock, args.resume) if args.resume else RunStore.create(config, lock, [])
            pipeline = Pipeline(store, config_path=args.config, dry_run=args.dry_run,
                                adapters=adapters, console=console, resume=bool(args.resume))
            return pipeline.run(apply=args.apply)
    except KeyboardInterrupt:
        console.write("Interrupción; conservar estado y reanudar la última ejecución.")
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        console.write(f"Fallo operativo: {exc}")
        if pipeline:
            console.write(f"Estado conservado: {pipeline.store.path}; reanudar con --resume {pipeline.store.manifest.run_id}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
