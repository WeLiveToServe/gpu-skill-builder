@echo off
set "_CLI_HARNESS_DIR=%CLI_HARNESS_DIR%"
if "%_CLI_HARNESS_DIR%"=="" set "_CLI_HARNESS_DIR=%USERPROFILE%\dev\cli-harness"
call "%_CLI_HARNESS_DIR%\codex-os.cmd" %*
