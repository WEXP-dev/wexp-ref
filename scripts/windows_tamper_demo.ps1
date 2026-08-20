[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Candidate,

    [Parameter(Mandatory = $true)]
    [string]$RelativeFile,

    [Parameter(Mandatory = $false)]
    [int]$Index = 0
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$WorkingDirectory = (Get-Location).Path
if ([System.IO.Path]::IsPathRooted($Candidate)) {
    $CandidatePath = [System.IO.Path]::GetFullPath($Candidate)
}
else {
    $CandidatePath = [System.IO.Path]::GetFullPath(
        (Join-Path -Path $WorkingDirectory -ChildPath $Candidate)
    )
}

if (-not (Test-Path -LiteralPath $CandidatePath -PathType Container)) {
    throw "Candidate directory does not exist: $CandidatePath"
}
if ([System.IO.Path]::IsPathRooted($RelativeFile)) {
    throw "RelativeFile must be relative to the candidate directory: $RelativeFile"
}

$TargetPath = [System.IO.Path]::GetFullPath(
    (Join-Path -Path $CandidatePath -ChildPath $RelativeFile)
)
$CandidatePrefix = $CandidatePath.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (-not $TargetPath.StartsWith(
    $CandidatePrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "RelativeFile escapes the candidate directory: $RelativeFile"
}
if (-not (Test-Path -LiteralPath $TargetPath -PathType Leaf)) {
    throw "Target file does not exist: $TargetPath"
}

$Bytes = [System.IO.File]::ReadAllBytes($TargetPath)
if ($Index -lt 0 -or $Index -ge $Bytes.Length) {
    throw "Index $Index is outside the valid byte range 0..$($Bytes.Length - 1): $TargetPath"
}

$Before = $Bytes[$Index]
$After = [byte]($Before -bxor 1)
$Bytes[$Index] = $After
[System.IO.File]::WriteAllBytes($TargetPath, $Bytes)

$Written = [System.IO.File]::ReadAllBytes($TargetPath)
if ($Written.Length -ne $Bytes.Length -or $Written[$Index] -ne $After) {
    throw "Mutation verification failed after writing: $TargetPath"
}

Write-Output (
    "MUTATION COMPLETE: {0} byte[{1}] 0x{2:X2} -> 0x{3:X2}" -f `
        $TargetPath, $Index, $Before, $After
)
