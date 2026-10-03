@echo off
REM Header/Footer Vision tagger — prompt for series ID
REM Local WAMP only. Requires OPENAI_API_KEY in platetag-api\.env
REM
REM Writes header_override + footer_override from plate images; sets updates_complete = 1.
REM Eligible plates: both overrides NULL/empty AND updates_complete = 0 AND has image.
REM
REM Optional: set LIMIT below before running, or enter at prompt.

cd /d C:\wamp64\www\platetag-api

set PHP=C:\wamp64\bin\php\php8.3.14\php.exe

echo.
echo ============================================================
echo   PlateTag Header/Footer Vision Tagger
echo   Command: tagger:header-footer-series {series_id}
echo ============================================================
echo.

set /p SERIES_ID="Enter series ID: "
if "%SERIES_ID%"=="" (
    echo Aborted — no series ID entered.
    pause
    exit /b 1
)

echo.
echo === Dry run — series %SERIES_ID% (no API, no DB writes) ===
"%PHP%" -d memory_limit=512M artisan tagger:header-footer-series %SERIES_ID% --dry-run
echo.

set /p GO="Run LIVE tagger for series %SERIES_ID%? Type YES to continue: "
if /I not "%GO%"=="YES" (
    echo Aborted.
    pause
    exit /b 1
)

echo.
set /p LIMIT="Optional plate limit for test run (press Enter for ALL eligible in series): "

if "%LIMIT%"=="" (
    echo === LIVE run — full series %SERIES_ID% ===
    "%PHP%" -d memory_limit=512M artisan tagger:header-footer-series %SERIES_ID%
) else (
    echo === LIVE run — series %SERIES_ID%, limit %LIMIT% ===
    "%PHP%" -d memory_limit=512M artisan tagger:header-footer-series %SERIES_ID% --limit=%LIMIT%
)

echo.
echo Done.
echo Failures (if any): storage\logs\tagger-header-footer-failures.log
echo Re-run the same series to retry failed plates (updates_complete stays 0 on failure).
echo.
echo Verify in phpMyAdmin:
echo   SELECT id, name, header_override, footer_override, updates_complete
echo   FROM plates WHERE series_id = %SERIES_ID% ORDER BY id;
echo.
pause
