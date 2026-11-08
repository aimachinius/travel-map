@echo off
chcp 65001 >nul
echo ========================================================
echo   KIỂM THỬ TỰ ĐỘNG TC_PERF_15: CLIENT PERFORMANCE
echo   Map Rendering (Leaflet) & Video Playback (TikTok)
echo ========================================================
echo.

set PYTHON_EXE=C:\Users\loing\AppData\Local\Python\pythoncore-3.10-64\python.exe
set SCRIPT_DIR=%~dp0

set ROUND=%1
if "%ROUND%"=="" set ROUND=1

set DURATION=%2
if "%DURATION%"=="" set DURATION=60

set MODE=%3
if "%MODE%"=="headed" (
    set HEADED_FLAG=--headed
    echo Chế độ: Mở cửa sổ trình duyệt trực quan (Headed Mode)
) else (
    set HEADED_FLAG=
    echo Chế độ: Chạy ngầm (Headless Mode)
)

echo Round kiểm thử: Round %ROUND%
echo Thời lượng: %DURATION% giây
echo.
echo Đang chạy kiểm thử TC_PERF_15...
"%PYTHON_EXE%" "%SCRIPT_DIR%run_tc_perf_15.py" --round %ROUND% --duration %DURATION% %HEADED_FLAG%

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Cập nhật báo cáo performance_testing.md và bao cao.md...
    "%PYTHON_EXE%" "%SCRIPT_DIR%generate_report.py"
    echo.
    echo ========================================================
    echo   HOÀN TẤT KIỂM THỬ TC_PERF_15 THÀNH CÔNG!
    echo ========================================================
) else (
    echo.
    echo [LỖI] Quá trình kiểm thử gặp sự cố, mã lỗi: %ERRORLEVEL%
)
pause

