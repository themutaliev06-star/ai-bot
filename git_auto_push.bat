@echo off
chcp 65001 >nul
echo [INFO] Starting GitHub synchronization...
echo.

:: Temporarily disable CRLF warnings
git config --local core.safecrlf false

:: Check if we're in git repo
git status >nul 2>&1
if errorlevel 1 (
    echo ERROR: Not a git repository or git not installed
    timeout /t 5
    exit /b 1
)

:: Check for changes
git diff --quiet && git diff --staged --quiet
if %errorlevel% equ 0 (
    echo [INFO] No changes to commit
    timeout /t 2
    exit /b 0
)

:: Show changes without warnings
echo [INFO] Changes found:
git -c core.safecrlf=false status --short 2>nul
echo.

:: Get commit message
set commit_msg=
set /p commit_msg="Enter commit message: "
if "%commit_msg%"=="" (
    for /f "tokens=1-3 delims=/" %%a in ('date /t') do set d=%%c-%%a-%%b
    for /f "tokens=1-2" %%a in ('time /t') do set t=%%a
    set "commit_msg=Auto commit: %d% %t%"
)

:: Execute git operations without CRLF warnings
echo [INFO] Committing changes...
git -c core.safecrlf=false add . >nul 2>&1
git -c core.safecrlf=false commit -m "%commit_msg%" >nul 2>&1

if %errorlevel% equ 0 (
    echo [INFO] Pushing to remote...
    git push >nul 2>&1
)

:: Restore original setting
git config --local core.safecrlf true

:: Check final result
if %errorlevel% equ 0 (
    echo [SUCCESS] Synchronization completed!
) else (
    echo [ERROR] Operation failed
    echo Possible issues:
    echo - Network connection
    echo - Git credentials
    echo - Remote repository access
)

timeout /t 3