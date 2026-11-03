"""Owned process trees for the local launcher (stdlib only)."""
from __future__ import annotations

import os
import signal
import subprocess


class _WindowsJob:
    """Keep descendants in a kill-on-close job, including an npm process that exits early."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w

        class Limits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", w.DWORD), ("min_working", ctypes.c_size_t),
                        ("max_working", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Limits), ("io", Counters), ("process_limit", ctypes.c_size_t),
                        ("job_limit", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.SetInformationJobObject.restype = w.BOOL
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.AssignProcessToJobObject.restype = w.BOOL
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach(self, process):
        import ctypes
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class ProcessGroup:
    def __init__(self):
        self.children = []
        self.job = None

    def start(self, args, *, cwd, env, shell=False):
        if os.name == "nt" and self.job is None:
            self.job = _WindowsJob()
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(args, cwd=cwd, env=env, shell=shell, **options)
        self.children.append(process)
        if self.job:
            try:
                self.job.attach(process)
            except OSError:
                # This is a child we just created; never target an unrelated port or PID.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                raise
        return process

    def stop(self):
        for process in self.children:
            try:
                if os.name == "nt":
                    if process.poll() is None:
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
        for process in self.children:
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                pass
        if self.job:
            self.job.close()
            self.job = None
        for process in self.children:
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                elif process.poll() is None:
                    process.kill()
            except (OSError, ProcessLookupError):
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        self.children.clear()
