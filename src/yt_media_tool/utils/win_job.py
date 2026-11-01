"""Windows Job Object：程式結束時一併終止所有子程序（ffmpeg.exe、deno.exe）。

FFmpeg 合併 / 轉檔進行中關閉程式時，yt-dlp 啟動的 ffmpeg.exe 不會隨 Python 結束；
將本程序加入設定 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE 的 Job，子程序會繼承 Job 成員資格，
程式結束（Job 最後一個 handle 關閉）時由系統一併終止，不會殘留背景程序鎖住檔案。

自動更新時則相反：安裝程式必須在本程式結束後繼續執行，因此先以 allow_children_to_outlive()
取消 KILL_ON_JOB_CLOSE 並允許子程序脫離 Job（JOB_OBJECT_LIMIT_BREAKAWAY_OK）。
注意 KILL_ON_JOB_CLOSE、BREAKAWAY_OK 屬於「延伸」限制，必須以 JobObjectExtendedLimitInformation 設定；
用 JobObjectBasicLimitInformation 設定時這些旗標不會被清除（v2.6.0 的自動更新因此失敗）。
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

_job_handle = None  # 保持 handle 直到程序結束

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x0800
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000


def _kernel32():
    """回傳 (ctypes, kernel32, JOBOBJECT_EXTENDED_LIMIT_INFORMATION 類別)；只在 Windows 呼叫。"""
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

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return ctypes, kernel32, JOBOBJECT_EXTENDED_LIMIT_INFORMATION


def _set_job_flags(flags: int) -> None:
    ctypes, kernel32, extended = _kernel32()
    info = extended()
    info.BasicLimitInformation.LimitFlags = flags
    if not kernel32.SetInformationJobObject(_job_handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                            ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]


def kill_children_on_exit() -> bool:
    global _job_handle
    if not sys.platform.startswith("win") or _job_handle is not None:
        return _job_handle is not None
    try:
        ctypes, kernel32, _ = _kernel32()
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        _job_handle = job
        _set_job_flags(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        return True
    except Exception:  # 失敗時僅記錄，不影響程式啟動
        _job_handle = None
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
        ctypes, kernel32, _ = _kernel32()
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        _mutex_handle = handle  # 保持 handle 直到程序結束
        return True
    except Exception:
        log.warning("無法建立程式 mutex，安裝程式將無法偵測程式是否執行中", exc_info=True)
        return False


def allow_children_to_outlive() -> bool:
    """取消「程式結束時終止子程序」並允許子程序脫離 Job，讓自動更新的安裝程式在本程式結束後繼續執行。

    只在即將關閉程式並安裝更新時呼叫；此時佇列已停止，不會再有 ffmpeg 子程序。
    """
    if not sys.platform.startswith("win") or _job_handle is None:
        return True
    try:
        _set_job_flags(JOB_OBJECT_LIMIT_BREAKAWAY_OK)  # 不含 KILL_ON_JOB_CLOSE
        return True
    except Exception:
        log.warning("無法取消 Job Object 的子程序終止設定", exc_info=True)
        return False


def release_app_mutex() -> None:
    """釋放程式 mutex，讓自動更新的安裝程式不會因「程式執行中」而停止。"""
    global _mutex_handle
    if not sys.platform.startswith("win") or _mutex_handle is None:
        return
    try:
        _, kernel32, _ = _kernel32()
        kernel32.CloseHandle(_mutex_handle)
    except Exception:
        log.warning("無法釋放程式 mutex", exc_info=True)
    _mutex_handle = None
