#Requires -Version 5.1
[CmdletBinding()]
param(
  [string]$SourceRoot = "",
  [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
  param([string]$Preferred)
  if ($Preferred -and (Test-Path -LiteralPath $Preferred)) {
    return (Resolve-Path -LiteralPath $Preferred).Path
  }
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c) { return $c }
  }
  foreach ($name in @("py", "python")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  throw "Python 3.11+ not found. Install Python or pass -PythonExe."
}

function Merge-UserMcp {
  param(
    [string]$McpPath,
    [string]$RuntimePython,
    [string]$ServerScript,
    [string]$ScriptsDir
  )

  $servers = @{}
  if (Test-Path -LiteralPath $McpPath) {
    $raw = Get-Content -LiteralPath $McpPath -Raw -Encoding UTF8
    if ($raw -and $raw.Trim()) {
      $parsed = $raw | ConvertFrom-Json
      if ($parsed.mcpServers) {
        $parsed.mcpServers.PSObject.Properties | ForEach-Object {
          $servers[$_.Name] = $_.Value
        }
      }
    }
  }

  $servers["fe4-oracle-readonly"] = [pscustomobject]@{
    command = $RuntimePython
    args    = @($ServerScript)
    env     = [pscustomobject]@{ PYTHONPATH = $ScriptsDir }
  }

  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine("{")
  [void]$sb.AppendLine('  "mcpServers": {')
  $names = @($servers.Keys)
  for ($i = 0; $i -lt $names.Count; $i++) {
    $name = $names[$i]
    $entry = $servers[$name]
    $cmd = ([string]$entry.command).Replace("\", "\\")
    $arg0 = ([string]$entry.args[0]).Replace("\", "\\")
    $pyPath = ([string]$entry.env.PYTHONPATH).Replace("\", "\\")
    [void]$sb.AppendLine(('    "{0}": {{' -f $name))
    [void]$sb.AppendLine(('      "command": "{0}",' -f $cmd))
    [void]$sb.AppendLine('      "args": [')
    [void]$sb.AppendLine(('        "{0}"' -f $arg0))
    [void]$sb.AppendLine("      ],")
    [void]$sb.AppendLine('      "env": {')
    [void]$sb.AppendLine(('        "PYTHONPATH": "{0}"' -f $pyPath))
    [void]$sb.AppendLine("      }")
    if ($i -lt $names.Count - 1) {
      [void]$sb.AppendLine("    },")
    } else {
      [void]$sb.AppendLine("    }")
    }
  }
  [void]$sb.AppendLine("  }")
  [void]$sb.AppendLine("}")

  $dir = Split-Path -Parent $McpPath
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
  Set-Content -LiteralPath $McpPath -Value $sb.ToString() -Encoding UTF8
}

if (-not $SourceRoot) {
  if ($PSScriptRoot) { $SourceRoot = $PSScriptRoot }
  else { $SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
}
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$TargetRoot = Join-Path $env:USERPROFILE ".cursor\plugins\local\fe4-oracle-readonly"
$UserMcp = Join-Path $env:USERPROFILE ".cursor\mcp.json"

Write-Host "Source: $SourceRoot"
Write-Host "Target: $TargetRoot"

if ($SourceRoot -ne $TargetRoot) {
  New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
  $exclude = @("runtime", ".git", "__pycache__", "secrets.local", "fe4-oracle-guard.log", ".venv")
  Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
    if ($exclude -contains $_.Name) { return }
    $dest = Join-Path $TargetRoot $_.Name
    if ($_.PSIsContainer) {
      if (Test-Path -LiteralPath $dest) {
        Remove-Item -LiteralPath $dest -Recurse -Force
      }
      Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
    } else {
      Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    }
  }
  Write-Host "Synced package files into local plugin folder."
} else {
  Write-Host "Already in local plugin folder; skipping copy."
}

$configPy = Join-Path $TargetRoot "scripts\config.py"
$configExample = Join-Path $TargetRoot "scripts\config.example.py"
if (-not (Test-Path -LiteralPath $configPy)) {
  Copy-Item -LiteralPath $configExample -Destination $configPy
  Write-Host "Created scripts\config.py from example."
}

$py = Resolve-Python -Preferred $PythonExe
Write-Host "Python: $py"

$runtime = Join-Path $TargetRoot "runtime"
$runtimePy = Join-Path $runtime "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $runtimePy)) {
  Write-Host "Creating runtime venv..."
  & $py -m venv $runtime
  if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}

Write-Host "Installing requirements into runtime..."
& $runtimePy -m pip install --upgrade pip --quiet
& $runtimePy -m pip install -r (Join-Path $TargetRoot "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$secrets = Join-Path $TargetRoot "secrets.local"
if (-not (Test-Path -LiteralPath $secrets)) {
  Copy-Item -LiteralPath (Join-Path $TargetRoot "secrets.local.example") -Destination $secrets
  Write-Host "IMPORTANT: Edit secrets.local and put the real password." -ForegroundColor Yellow
}

$serverScript = Join-Path $TargetRoot "scripts\mcp_server.py"
$scriptsDir = Join-Path $TargetRoot "scripts"
Merge-UserMcp -McpPath $UserMcp -RuntimePython $runtimePy -ServerScript $serverScript -ScriptsDir $scriptsDir
Write-Host "Registered MCP in $UserMcp"

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  1. Ensure secrets.local has the real password"
Write-Host "  2. Review scripts\config.py"
Write-Host "  3. Cursor: Developer: Reload Window"
Write-Host "  4. MCP fe4-oracle-readonly = Connected (User)"
Write-Host "  5. Plugin shows Rules, Skills, and Hooks"
