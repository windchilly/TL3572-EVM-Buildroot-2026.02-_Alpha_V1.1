param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot '.git'))) { throw 'Not the project repository' }
$plan = Get-Content -LiteralPath (Join-Path $repositoryRoot 'docs/operations/local-reorganization-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json

function ProjectPath([string]$RelativePath) {
    $full = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $RelativePath))
    if (-not $full.StartsWith($repositoryRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Outside repository: $RelativePath"
    }
    $cursor = $full
    while ($cursor.Length -gt $repositoryRoot.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Reparse point is not a maintenance target: $cursor"
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

$report = ProjectPath '.local-only/maintenance/local-reorganization-20260928.json'
if ($Apply -and (Test-Path -LiteralPath $report)) { throw 'Action report exists; do not reapply this dated plan' }
foreach ($move in $plan.moves) {
    $source = ProjectPath $move.source
    $destination = ProjectPath $move.destination
    if (-not (Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
    if (Test-Path -LiteralPath $destination) { throw "Destination already exists: $destination" }
    foreach ($item in (Get-ChildItem -LiteralPath $source -Recurse -Force)) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point: $($item.FullName)" }
    }
}
foreach ($entry in $plan.recycle) {
    $path = ProjectPath $entry.source
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing recycle target: $path" }
}
foreach ($relative in $plan.remove_empty_roots) { $null = ProjectPath $relative }
if (-not $Apply) {
    foreach ($move in $plan.moves) { "MOVE $($move.source) -> $($move.destination)" }
    foreach ($entry in $plan.recycle) { "RECYCLE $($entry.source)" }
    'Remove only empty legacy directories; keep stage and reproduction trees unchanged.'
    return
}

# Hash every moved file before doing anything, including ignored firmware/tools.
$inventory = @()
foreach ($move in $plan.moves) {
    $source = ProjectPath $move.source
    $isDirectory = (Get-Item -LiteralPath $source -Force).PSIsContainer
    $files = if ($isDirectory) { @(Get-ChildItem -LiteralPath $source -Recurse -File -Force) } else { @(Get-Item -LiteralPath $source -Force) }
    foreach ($file in $files) {
        $suffix = if ($isDirectory) { '/' + $file.FullName.Substring($source.Length + 1).Replace('\', '/') } else { '' }
        $inventory += [pscustomobject]@{source=($move.source + $suffix); destination=($move.destination + $suffix); bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
}
$recycled = @()
foreach ($entry in $plan.recycle) {
    $path = ProjectPath $entry.source
    $recycled += [pscustomobject]@{source=$entry.source; bytes=(Get-Item -LiteralPath $path).Length; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant(); reason=$entry.reason}
}
$actions = @()
$verified = 0
New-Item -ItemType Directory -Path (Split-Path -Parent $report) -Force | Out-Null
Add-Type -AssemblyName Microsoft.VisualBasic
try {
    foreach ($move in $plan.moves) {
        $source = ProjectPath $move.source
        $destination = ProjectPath $move.destination
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Move-Item -LiteralPath $source -Destination $destination
        $actions += [pscustomobject]@{action='move'; source=$move.source; destination=$move.destination}
        "MOVED $($move.source) -> $($move.destination)"
    }
    foreach ($entry in $plan.recycle) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile((ProjectPath $entry.source),
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        $actions += [pscustomobject]@{action='recycle'; source=$entry.source}
        "RECYCLED $($entry.source)"
    }
    foreach ($relative in $plan.remove_empty_roots) {
        $path = ProjectPath $relative
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $directories = @(Get-ChildItem -LiteralPath $path -Recurse -Directory -Force | Sort-Object { $_.FullName.Length } -Descending)
        foreach ($directory in $directories) {
            if (@(Get-ChildItem -LiteralPath $directory.FullName -Force).Count -eq 0) { Remove-Item -LiteralPath $directory.FullName }
        }
        if (@(Get-ChildItem -LiteralPath $path -Force).Count -ne 0) { throw "Unexpected remaining contents: $path" }
        Remove-Item -LiteralPath $path
        $actions += [pscustomobject]@{action='remove-empty-directory'; source=$relative}
    }
    foreach ($entry in $inventory) {
        $path = ProjectPath $entry.destination
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
            throw "Moved file differs: $($entry.destination)"
        }
        $verified++
    }
    "PASS: $verified moved files have identical SHA256 values"
} finally {
    [pscustomobject]@{schema=1; baseline_commit=$plan.baseline_commit; moved_files=$inventory.Count; verified_files=$verified; actions=$actions; inventory=$inventory; recycled=$recycled} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $report -Encoding UTF8
    "Action report: $report"
}
