$ErrorActionPreference = "Stop"

Write-Host "Running Python tests..."
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tests

Write-Host "Compiling Python files..."
python -m compileall -q app server services scripts

Write-Host "Checking frontend JavaScript..."
Get-ChildItem -Recurse server/static/js -Filter *.js | ForEach-Object {
    node --check $_.FullName
}

Write-Host "All checks passed."
