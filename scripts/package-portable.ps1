$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& "$PSScriptRoot\build-bridge.ps1"

npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm run tauri:build -- --no-bundle
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$version = (Get-Content "$root\src-tauri\tauri.conf.json" | ConvertFrom-Json).version
$releaseDir = Join-Path $root "src-tauri\target\release"
$portableRoot = Join-Path $root ".build\portable"
$portableAppDir = Join-Path $portableRoot "AutoGreenBackground"
$zipOutDir = Join-Path $root "dist-portable"
$zipName = "AutoGreenBackground-win-x64-v$version-portable.zip"
$zipPath = Join-Path $zipOutDir $zipName

New-Item -ItemType Directory -Force -Path $portableAppDir | Out-Null
New-Item -ItemType Directory -Force -Path $zipOutDir | Out-Null

Copy-Item -Force (Join-Path $releaseDir "auto-green-background-tauri.exe") $portableAppDir
Copy-Item -Recurse -Force (Join-Path $releaseDir "_up_") $portableAppDir
New-Item -ItemType Directory -Force -Path (Join-Path $portableAppDir "_up_\bridge") | Out-Null
Copy-Item -Recurse -Force (Join-Path $root "src-tauri\bin\bridge\*") (Join-Path $portableAppDir "_up_\bridge")

if (Test-Path $zipPath) {
  Remove-Item -Force $zipPath
}

for ($i = 0; $i -lt 5; $i++) {
  try {
    Compress-Archive -Path "$portableAppDir\*" -DestinationPath $zipPath -CompressionLevel Optimal -Force
    break
  } catch {
    if ($i -eq 4) {
      throw
    }
    Start-Sleep -Seconds (2 + $i)
  }
}

Write-Host "Portable package created: $zipPath"
