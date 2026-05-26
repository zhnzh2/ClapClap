$ErrorActionPreference = "Stop"

Write-Host "Running Python tests..."
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Compiling Python files..."
python -m compileall -q app server scripts tests
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Checking frontend JavaScript..."
$jsFailed = $false
Get-ChildItem -Recurse server/static/js -Filter *.js | ForEach-Object {
    node --check $_.FullName
    if ($LASTEXITCODE -ne 0) {
        $jsFailed = $true
    }
}

if ($jsFailed) {
    exit 1
}

Write-Host "All checks passed."
