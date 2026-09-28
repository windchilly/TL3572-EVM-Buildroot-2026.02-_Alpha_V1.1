param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot '.git'))) { throw 'Not the project repository' }

function ProjectPath([string]$RelativePath) {
    $full = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $RelativePath))
    if (-not $full.StartsWith($repositoryRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Outside repository: $RelativePath"
    }
    $cursor = $full
    while ($cursor.Length -gt $repositoryRoot.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Reparse point is not a cleanup target: $cursor"
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

$moves = @(
    @('.local-git-metadata-backup', '.local-only/metadata/nested-vendor-git'),
    @('4-软件资料/Linux/LinuxSDK/LinuxSDK-v1.0.tar.gz', '.local-only/vendor-sdk/LinuxSDK-v1.0.tar.gz'),
    @('4-软件资料/Linux/LinuxSDK/dl.tar.gz', '.local-only/vendor-sdk/dl.tar.gz'),
    @('4-软件资料/Linux/LinuxSDK/rk3572-buildroot-2026.02-sysroot-v1.0.tar.gz', '.local-only/vendor-sdk/rk3572-buildroot-2026.02-sysroot-v1.0.tar.gz')
)
$recycle = @(
    '4-软件资料/Tools/Windows/ubuntu-22.04.4-desktop-amd64.iso',
    '4-软件资料/Tools/Windows/VMware-workstation-full-16.2.5-20904516.exe'
)
$caches = @(
    'repro-inputs/all-stages/scripts/__pycache__',
    'repro-inputs/all-stages/tests/__pycache__',
    'stages/stage07-peripheral-partition/source/host/__pycache__',
    'stages/stage07-peripheral-partition/tests/__pycache__',
    'stages/stage07-peripheral-partition/tests/board/__pycache__'
)
$duplicate = '4-软件资料/Linux/U-Boot/src/u-boot-2025.04-v1.0-gb501dba.tar(1).gz'
$keeper = '4-软件资料/Linux/U-Boot/src/u-boot-2025.04-v1.0-gb501dba.tar.gz'
$report = ProjectPath '.local-only/maintenance/local-layout-20260928.json'
if ($Apply -and (Test-Path -LiteralPath $report)) { throw 'Previous action report exists; do not overwrite or reapply blindly' }

# Complete the safety checks before changing any file. No tracked source is deleted.
foreach ($pair in $moves) {
    $source = ProjectPath $pair[0]; $destination = ProjectPath $pair[1]
    if ((Test-Path -LiteralPath $source) -and (Test-Path -LiteralPath $destination)) { throw "Destination exists: $destination" }
}
foreach ($relative in ($recycle + $caches + @($duplicate, $keeper))) { $null = ProjectPath $relative }
if (Test-Path -LiteralPath (ProjectPath $duplicate)) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (ProjectPath $duplicate)).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath (ProjectPath $keeper)).Hash) { throw 'U-Boot archives differ' }
}
foreach ($relative in $caches) {
    $path = ProjectPath $relative
    if (Test-Path -LiteralPath $path) {
        foreach ($item in (Get-ChildItem -LiteralPath $path -Recurse -Force)) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or (-not $item.PSIsContainer -and $item.Extension -ne '.pyc')) {
                throw "Unexpected content in bytecode cache: $($item.FullName)"
            }
        }
    }
}
if (-not $Apply) {
    foreach ($pair in $moves) { "MOVE $($pair[0]) -> $($pair[1])" }
    foreach ($relative in $recycle) { "RECYCLE $relative" }
    "DELETE verified duplicate $duplicate (recoverable from $keeper)"
    foreach ($relative in $caches) { "DELETE regenerable bytecode cache $relative" }
    return
}

Add-Type -AssemblyName Microsoft.VisualBasic
$actions = @()
New-Item -ItemType Directory -Path (Split-Path -Parent $report) -Force | Out-Null
try {
    foreach ($pair in $moves) {
        $source = ProjectPath $pair[0]; $destination = ProjectPath $pair[1]
        if (-not (Test-Path -LiteralPath $source)) { continue }
        $bytes = (Get-ChildItem -LiteralPath $source -File -Recurse -Force | Measure-Object Length -Sum).Sum
        if (-not (Get-Item -LiteralPath $source).PSIsContainer) { $bytes = (Get-Item -LiteralPath $source).Length }
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Move-Item -LiteralPath $source -Destination $destination
        $actions += [pscustomobject]@{action='move'; source=$pair[0]; destination=$pair[1]; bytes=$bytes}
        "MOVED $($pair[0])"
    }
    foreach ($relative in $recycle) {
        $path = ProjectPath $relative
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $bytes = (Get-Item -LiteralPath $path).Length
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($path,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        $actions += [pscustomobject]@{action='recycle'; source=$relative; bytes=$bytes}
        "RECYCLED $relative"
    }
    if (Test-Path -LiteralPath (ProjectPath $duplicate)) {
        $bytes = (Get-Item -LiteralPath (ProjectPath $duplicate)).Length
        Remove-Item -LiteralPath (ProjectPath $duplicate)
        $actions += [pscustomobject]@{action='delete-identical-copy'; source=$duplicate; recover_from=$keeper; bytes=$bytes}
    }
    foreach ($relative in $caches) {
        $path = ProjectPath $relative
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $bytes = (Get-ChildItem -LiteralPath $path -File -Recurse -Force | Measure-Object Length -Sum).Sum
        Remove-Item -LiteralPath $path -Recurse -Force
        $actions += [pscustomobject]@{action='delete-regenerable-bytecode'; source=$relative; bytes=$bytes}
    }
} finally {
    ConvertTo-Json -Depth 4 -InputObject @($actions) | Set-Content -LiteralPath $report -Encoding UTF8
    "Action report: $report"
}
