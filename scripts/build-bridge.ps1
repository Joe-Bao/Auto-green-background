$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $root ".build\bridge"
$distDir = Join-Path $buildRoot "dist"
$workDir = Join-Path $buildRoot "work"
$specDir = Join-Path $buildRoot "spec"
$outDir = Join-Path $root "src-tauri\bin\bridge"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

uv run --with pyinstaller pyinstaller `
  --clean `
  --noconfirm `
  --onedir `
  --name bridge `
  --distpath "$distDir" `
  --workpath "$workDir" `
  --specpath "$specDir" `
  --collect-all cv2 `
  --collect-all numpy `
  "$root\tauri_bridge.py"

$bridgeExe = Join-Path $distDir "bridge\bridge.exe"
if (!(Test-Path $bridgeExe)) {
  throw "bridge.exe was not generated at $bridgeExe"
}

Remove-Item -Recurse -Force $outDir
Copy-Item -Recurse -Force (Join-Path $distDir "bridge") $outDir
Write-Host "bridge runtime ready at src-tauri/bin/bridge/"
