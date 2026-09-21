param([Parameter(ValueFromRemainingArguments = $true)][string[]]$NpmArguments)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$nodeExecutable = (Get-Command node.exe -ErrorAction Stop).Source
$nodeMajor = [int]((& $nodeExecutable --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 24) {
    $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (!(Test-Path -LiteralPath $bundledNode)) { throw 'Install Node.js 24 or newer to run this project.' }
    $nodeExecutable = $bundledNode
}
$npmDirectory = Split-Path -Parent (Get-Command npm.cmd -ErrorAction Stop).Source
$npmCli = Join-Path $npmDirectory 'node_modules\npm\bin\npm-cli.js'
if (!(Test-Path -LiteralPath $npmCli)) { throw 'npm-cli.js was not found. Install Node.js with npm.' }
$previousPath = $env:Path
Push-Location -LiteralPath $projectRoot
try {
    $env:Path = (Split-Path -Parent $nodeExecutable) + ';' + $env:Path
    & $nodeExecutable $npmCli @NpmArguments
    $resultCode = $LASTEXITCODE
} finally {
    $env:Path = $previousPath
    Pop-Location
}
exit $resultCode
