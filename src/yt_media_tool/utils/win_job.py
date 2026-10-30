"""Windows Job Object：程式結束時一併終止所有子程序（ffmpeg.exe、deno.exe）。

FFmpeg 合併 / 轉檔進行中關閉程式時，yt-dlp 啟動的 ffmpeg.exe 不會隨 Python 結束；
將本程序加入設定 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE 的 Job，子程序會繼承 Job 成員資格，
程式結束（Job 最後一個 handle 關閉）時由系統一併終止，不會殘留背景程序鎖住檔案。
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

_job_handle = None  # 保持 handle 直到程序結束


def kill_children_on_exit() -> bool:
    global _job_handle
    if not sys.platform.startswith("win") or _job_handle is not None:
        return _job_handle is not None
    try:
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        job_object_extended_limit_information = 9
        job_object_limit_kill_on_job_close = 0x2000

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = job_object_limit_kill_on_job_close
        if not kernel32.SetInformationJobObject(job, job_object_extended_limit_information,
                                                ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        _job_handle = job
        return True
    except Exception:  # 失敗時僅記錄，不影響程式啟動
        log.warning("無法建立 Windows Job Object，關閉時可能殘留 ffmpeg 子程序", exc_info=True)
        return False


APP_MUTEX_NAME = "YTMediaTool_AppMutex"  # 須與 packaging/installer.iss 的 AppMutex 相同
_mutex_handle = None


def create_app_mutex(name: str = APP_MUTEX_NAME) -> bool:
    """建立具名 mutex，讓安裝 / 解除安裝程式能偵測程式是否仍在執行並提示使用者關閉。"""
    global _mutex_handle
    if not sys.platform.startswith("win") or _mutex_handle is not None:
        return _mutex_handle is not None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        _mutex_handle = handle  # 保持 handle 直到程序結束
        return True
    except Exception:
        log.warning("無法建立程式 mutex，安裝程式將無法偵測程式是否執行中", exc_info=True)
        return False
