# Build ClaudeBridge and deploy it into the game's local mod folder.
#
#   pwsh mod/build.ps1
#
# `shapez 2.exe --set-modding-env-vars` writes SPZ2_PATH / SPZ2_SHIFTER /
# SPZ2_PERSISTENT to the USER environment, which a fresh shell does not necessarily
# inherit -- MSBuild then silently fails to resolve the game assemblies and the
# errors look like missing namespaces rather than missing references.  So read them
# out of the registry every time.
$ErrorActionPreference = 'Stop'
foreach ($v in 'SPZ2_PATH', 'SPZ2_SHIFTER', 'SPZ2_PERSISTENT') {
    $val = [Environment]::GetEnvironmentVariable($v, 'User')
    if (-not $val) { throw "$v is not set. Run: `"shapez 2.exe`" --set-modding-env-vars" }
    Set-Item -Path "env:$v" -Value $val
}
Write-Host "game assemblies : $env:SPZ2_PATH"
Write-Host "shifter         : $env:SPZ2_SHIFTER"
Write-Host "deploy target   : $env:SPZ2_PERSISTENT\mods\ClaudeBridge"
dotnet build (Join-Path $PSScriptRoot 'ClaudeBridge\ClaudeBridge.csproj') -v minimal
if ($LASTEXITCODE -ne 0) { throw "build failed" }
Get-ChildItem "$env:SPZ2_PERSISTENT\mods\ClaudeBridge" | Format-Table Name, Length -AutoSize
Write-Host "Restart Shapez 2, enable ClaudeBridge in the Mod Manager, load the sandbox,"
Write-Host "then press F1 and run:  claudebridge.status"
