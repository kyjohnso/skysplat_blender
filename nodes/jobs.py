"""Background-job infrastructure for non-blocking node execution.

A NodeJob runs a node's heavy work (subprocess orchestration, file IO —
anything that does NOT touch the bpy API) on a worker thread so Blender's
UI stays responsive. The owning modal operator (SKYSPLAT_NODE_OT_run)
polls the job from a timer on the main thread and writes results back into
node properties there, where bpy access is safe.

The split is deliberate: build_job() gathers everything off the bpy node
on the main thread and hands the worker a closure over plain data. The
worker must never touch bpy.
"""
from __future__ import annotations

import threading
from typing import Callable


class NodeJob:
    """A unit of off-thread work produced by a node's build_job().

    work: a callable taking a single `register_proc` argument and returning
          the node's output lineage dict. It MUST NOT touch bpy. If it
          launches a subprocess it may call register_proc(popen) so the job
          can terminate it on cancel.
    params: the node's params_dict(), forwarded to store_output() on success.
    """

    def __init__(self, work: Callable[[Callable], dict], params: dict):
        self._work = work
        self.params = params
        self.result: dict | None = None
        self.error: BaseException | None = None
        self.finished = False
        self._thread: threading.Thread | None = None
        self._proc = None
        self._lock = threading.Lock()

    def _register_proc(self, proc) -> None:
        with self._lock:
            self._proc = proc

    def start(self) -> None:
        """Run the work on a daemon worker thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self.result = self._work(self._register_proc)
        except BaseException as exc:  # noqa: BLE001 — surfaced to caller via .error
            self.error = exc
        finally:
            self.finished = True

    def run_blocking(self) -> dict:
        """Execute the work synchronously on the calling thread.

        Lets a node's run() reuse the exact same work logic the modal path
        runs off-thread, so there's a single source of truth.
        """
        return self._work(self._register_proc)

    def cancel(self) -> None:
        """Terminate the registered subprocess, if any is still running."""
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
