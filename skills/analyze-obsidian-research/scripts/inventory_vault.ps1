[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VaultRoot,

    [string[]]$Keywords = @(),

    [ValidateRange(1, 100000)]
    [int]$MaxFiles = 20000,

    [string]$OutFile
)

$ErrorActionPreference = 'Stop'

$resolvedRoot = (Resolve-Path -LiteralPath $VaultRoot).Path
$areaNames = @('文献', '数据', '项目', '任务', '论文产出管理')
$patterns = @($Keywords | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { [regex]::Escape($_.Trim()) })

function Test-KeywordMatch {
    param([string]$Text)

    if ($patterns.Count -eq 0) {
        return $true
    }

    foreach ($pattern in $patterns) {
        if ($Text -match $pattern) {
            return $true
        }
    }

    return $false
}

$directories = [System.Collections.Generic.List[object]]::new()
$files = [System.Collections.Generic.List[object]]::new()
$totalMatchingFiles = 0

foreach ($areaName in $areaNames) {
    $areaPath = Join-Path $resolvedRoot $areaName
    if (-not (Test-Path -LiteralPath $areaPath -PathType Container)) {
        continue
    }

    foreach ($directory in Get-ChildItem -LiteralPath $areaPath -Directory -Recurse -Force -ErrorAction SilentlyContinue) {
        $relativePath = $directory.FullName.Substring($resolvedRoot.Length).TrimStart([char]92, [char]47)
        if (Test-KeywordMatch -Text $relativePath) {
            $directories.Add([ordered]@{
                area = $areaName
                relative_path = $relativePath.Replace([char]92, [char]47)
            })
        }
    }

    foreach ($file in Get-ChildItem -LiteralPath $areaPath -File -Recurse -Force -ErrorAction SilentlyContinue) {
        $relativePath = $file.FullName.Substring($resolvedRoot.Length).TrimStart([char]92, [char]47)
        if (-not (Test-KeywordMatch -Text $relativePath)) {
            continue
        }

        $totalMatchingFiles++
        if ($files.Count -ge $MaxFiles) {
            continue
        }

        $files.Add([ordered]@{
            area = $areaName
            relative_path = $relativePath.Replace([char]92, [char]47)
            extension = $file.Extension.ToLowerInvariant()
            size_bytes = $file.Length
            last_modified = $file.LastWriteTime.ToString('yyyy-MM-ddTHH:mm:ssK')
        })
    }
}

$result = [ordered]@{
    vault_root = $resolvedRoot.Replace([char]92, [char]47)
    generated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    keywords = @($Keywords)
    areas_checked = $areaNames
    directories = @($directories | Sort-Object { $_.relative_path })
    files = @($files | Sort-Object { $_.relative_path })
    total_matching_files = $totalMatchingFiles
    truncated = ($totalMatchingFiles -gt $MaxFiles)
}

$json = $result | ConvertTo-Json -Depth 6
if (-not [string]::IsNullOrWhiteSpace($OutFile)) {
    $outPath = [System.IO.Path]::GetFullPath(
        $(if ([System.IO.Path]::IsPathRooted($OutFile)) { $OutFile } else { Join-Path $resolvedRoot $OutFile })
    )
    $rootPrefix = $resolvedRoot.TrimEnd([char]92, [char]47) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $outPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "OutFile must remain inside the vault root: $outPath"
    }
    $parent = Split-Path -Parent $outPath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($outPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}
$json
