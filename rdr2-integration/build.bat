@echo off
setlocal

set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
set "SDK_INC=C:\Games\Mods\RDR2\SDK\SDK\inc"
set "SDK_LIB=C:\Games\Mods\RDR2\SDK\SDK\lib"
set "RDR2_DIR=C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"

call "%VS_PATH%\VC\Auxiliary\Build\vcvars64.bat" >nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to initialize Visual C++ environment.
    exit /b 1
)

cd /d "%~dp0"

echo [BUILD] Compiling VoiceNPC.asi ...
cl.exe /nologo /O2 /MD /EHsc /W3 /std:c++17 ^
    /I "%SDK_INC%" ^
    main.cpp ^
    /link ^
    /DLL ^
    /LIBPATH:"%SDK_LIB%" ^
    ScriptHookRDR2.lib ^
    user32.lib ^
    ws2_32.lib ^
    xinput.lib ^
    /OUT:VoiceNPC.asi

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] VoiceNPC.asi built successfully!
    echo [DEPLOY] Copying to RDR2 game folder...
    copy /Y VoiceNPC.asi "%RDR2_DIR%\VoiceNPC.asi"
    echo [DEPLOY] Ready! VoiceNPC.asi deployed to Red Dead Redemption 2.
) else (
    echo [ERROR] Build failed!
    exit /b %ERRORLEVEL%
)
