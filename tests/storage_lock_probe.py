"""Controlled real Win32 delete-sharing lock, not attribution of historical failures."""

import ctypes
import json
import threading
import time
from ctypes import wintypes

from scholar_graph.atomic_io import windows_retry


def probe(root):
    root.mkdir(parents=True, exist_ok=False)
    source, target = root / ".pending-controlled", root / "published"
    source.mkdir()
    (source / "record.json").write_text('{"complete":true}', encoding="utf-8")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # FILE_SHARE_READ|WRITE, deliberately no FILE_SHARE_DELETE; backup semantics opens a directory.
    handle = kernel.CreateFileW(str(source), 1, 3, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        try:
            source.rename(target)
        except OSError as error:
            original = {"winerror": error.winerror, "message": str(error)}
        else:
            raise AssertionError("Native rename unexpectedly succeeded while delete-sharing was denied")
        def release():
            time.sleep(0.12)
            kernel.CloseHandle(handle)
        thread = threading.Thread(target=release)
        thread.start()
        retries = []
        def rename():
            try:
                return source.rename(target)
            except OSError as error:
                retries.append(error.winerror)
                raise
        windows_retry(rename)
        thread.join()
        handle = None
        assert json.loads((target / "record.json").read_text(encoding="utf-8")) == {"complete": True}
        return {"native_without_retry": original, "retry_error_codes": retries,
                "released_after_seconds": 0.12, "published_complete": True,
                "scope": "人为创建真实共享锁，证明机制与缓解；未定位历史错误的占用进程。"}
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)
