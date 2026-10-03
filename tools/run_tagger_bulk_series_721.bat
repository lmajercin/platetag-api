@echo off

REM Bulk Vision tagger — series 721 (Maryland Specialty)

REM Local WAMP only. Requires OPENAI_API_KEY in platetag-api\.env

REM

REM Edit --limit= below for test runs. Remove --limit for full series.



cd /d C:\wamp64\www\platetag-api



set PHP=C:\wamp64\bin\php\php8.3.14\php.exe



echo.

echo === Dry run (no API, no DB writes) ===

"%PHP%" -d memory_limit=512M artisan tagger:bulk-series 721 --dry-run

echo.



set /p GO="Run LIVE tagger for series 721? Type YES to continue: "

if /I not "%GO%"=="YES" (

    echo Aborted.

    pause

    exit /b 1

)



echo.

echo === LIVE run — limit 5 plates (edit .bat to change) ===

"%PHP%" -d memory_limit=512M artisan tagger:bulk-series 721 --limit=5



echo.

echo Done. Run maryland_vision_bulk_series_721_VERIFY.sql in phpMyAdmin to confirm.

pause

