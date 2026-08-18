#Requires -Version 5.1
[CmdletBinding()]
param(
  [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$ServerId = "fe4-oracle-readonly"
$TargetRoot = Join-Path $env:USERPROFILE ".cursor\plugins\local\$ServerId"
$UserMcp = Join-Path $env:USERPROFILE ".cursor\mcp.json"

function Write-UserMcp {
  param(
    [string]$McpPath,
    [hashtable]$Servers
  )

  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine("{")
  [void]$sb.AppendLine('  "mcpServers": {')
  $names = @($Servers.Keys)
  for ($i = 0; $i -lt $names.Count; $i++) {
    $name = $names[$i]
    $entry = $Servers[$name]
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

  if ($WhatIf) {
    Write-Host "[WhatIf] Would rewrite $McpPath ($($names.Count) server(s) remaining)"
    return
  }
  Set-Content -LiteralPath $McpPath -Value $sb.ToString() -Encoding UTF8
}

function Stop-PluginRuntimeProcesses {
  param([string]$PluginRoot)

  $needle = $PluginRoot.TrimEnd('\')
  $stopped = @()
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
    $procId = $_.ProcessId
    $procName = $_.Name
    $exe = [string]$_.ExecutablePath
    $cmd = [string]$_.CommandLine
    $hit = $false
    if ($exe -and $exe.StartsWith($needle, [System.StringComparison]::OrdinalIgnoreCase)) { $hit = $true }
    if (-not $hit -and $cmd -and $cmd.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { $hit = $true }
    if (-not $hit) { return }

    if ($WhatIf) {
      Write-Host ("[WhatIf] Would stop PID {0} ({1})" -f $procId, $procName)
      return
    }
    try {
      Stop-Process -Id $procId -Force -ErrorAction Stop
      $stopped += $procId
    } catch {
      Write-Host ("Could not stop PID {0}: {1}" -f $procId, $_.Exception.Message) -ForegroundColor Yellow
    }
  }
  if (-not $WhatIf -and $stopped.Count -gt 0) {
    Write-Host ("Stopped {0} process(es) using the plugin runtime: {1}" -f $stopped.Count, ($stopped -join ", "))
    Start-Sleep -Seconds 1
  } elseif (-not $WhatIf) {
    Write-Host "No running processes found using the plugin runtime."
  }
}

function Remove-PluginFolder {
  param([string]$Path)

  $scriptRoot = ""
  if ($PSScriptRoot) { $scriptRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path }
  $targetResolved = (Resolve-Path -LiteralPath $Path).Path

  if ($scriptRoot -and ($scriptRoot -eq $targetResolved)) {
    Set-Location $env:USERPROFILE
    $escaped = $targetResolved.Replace("'", "''")
    $cmd = "Start-Sleep -Seconds 1; Remove-Item -LiteralPath '$escaped' -Recurse -Force -ErrorAction SilentlyContinue"
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", $cmd) -WindowStyle Hidden | Out-Null
    Write-Host "Scheduled removal of plugin folder (script was running from inside it)."
    return
  }

  $attempts = 3
  for ($i = 1; $i -le $attempts; $i++) {
    try {
      Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
      Write-Host "Removed plugin folder (including secrets.local if present)."
      return
    } catch {
      if ($i -eq $attempts) { throw }
      Write-Host ("Delete attempt {0} failed (file in use). Retrying..." -f $i) -ForegroundColor Yellow
      Stop-PluginRuntimeProcesses -PluginRoot $Path
      Start-Sleep -Seconds 2
    }
  }
}

Write-Host "Uninstall target: $TargetRoot"
Write-Host "User MCP:         $UserMcp"

# 1) Remove only this server from user mcp.json (leave other MCP servers alone).
if (Test-Path -LiteralPath $UserMcp) {
  $raw = Get-Content -LiteralPath $UserMcp -Raw -Encoding UTF8
  $servers = @{}
  $hadEntry = $false
  if ($raw -and $raw.Trim()) {
    $parsed = $raw | ConvertFrom-Json
    if ($parsed.mcpServers) {
      $parsed.mcpServers.PSObject.Properties | ForEach-Object {
        if ($_.Name -eq $ServerId) {
          $hadEntry = $true
        } else {
          $servers[$_.Name] = $_.Value
        }
      }
    }
  }
  if ($hadEntry) {
    Write-UserMcp -McpPath $UserMcp -Servers $servers
    if ($WhatIf) {
      Write-Host "[WhatIf] Would remove '$ServerId' from mcp.json ($($servers.Count) other server(s) kept)."
    } else {
      Write-Host "Removed '$ServerId' from mcp.json ($($servers.Count) other server(s) kept)."
    }
  } else {
    Write-Host "No '$ServerId' entry in mcp.json."
  }
} else {
  Write-Host "No user mcp.json found."
}

# 2) Stop MCP python processes that lock runtime DLLs, then delete the plugin folder.
if (Test-Path -LiteralPath $TargetRoot) {
  $targetResolved = (Resolve-Path -LiteralPath $TargetRoot).Path
  Stop-PluginRuntimeProcesses -PluginRoot $targetResolved

  if ($WhatIf) {
    Write-Host "[WhatIf] Would remove $TargetRoot (includes secrets.local if present)"
  } else {
    try {
      Remove-PluginFolder -Path $TargetRoot
    } catch {
      Write-Host ""
      Write-Host "Could not delete the plugin folder because a file is still locked." -ForegroundColor Red
      Write-Host "Close Cursor (or disable the MCP server) and run uninstall.ps1 again." -ForegroundColor Yellow
      throw
    }
  }
} else {
  Write-Host "Plugin folder already absent."
}

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  1. Cursor: Developer: Reload Window"
Write-Host ("  2. Confirm MCP '{0}' is gone and the local plugin no longer appears" -f $ServerId)
Write-Host "  3. Clone / GitHub source is untouched - run install.ps1 again whenever you want"
