$ErrorActionPreference = "Stop"

Write-Host "Running Python tests..."
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Validating persisted data compatibility..."
python scripts/validate_data.py --strict --summary
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Compiling Python files..."
$env:PYTHONPYCACHEPREFIX = Join-Path (Get-Location) "test_artifacts\pycache"
python -m compileall -q app server scripts
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$pyCompileFailed = $false
Get-ChildItem tests -Filter *.py -File | ForEach-Object {
    python -m py_compile $_.FullName
    if ($LASTEXITCODE -ne 0) {
        $pyCompileFailed = $true
    }
}

if ($pyCompileFailed) {
    exit 1
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

Write-Host "Checking inline template JavaScript..."
$inlineFailed = $false
Get-ChildItem -Recurse server/templates -Filter *.html | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $matches = [regex]::Matches($content, '(?is)<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>')
    $index = 0
    foreach ($match in $matches) {
        $index += 1
        $script = $match.Groups[1].Value
        $script = [regex]::Replace($script, '{{.*?}}', 'null')
        $tempFile = Join-Path $env:TEMP ("clapclap-inline-{0}-{1}.js" -f $_.BaseName, $index)
        Set-Content -LiteralPath $tempFile -Value $script -Encoding UTF8
        node --check $tempFile
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Inline JavaScript failed: $($_.FullName) block $index"
            $inlineFailed = $true
        }
        Remove-Item -LiteralPath $tempFile -Force
    }
}

if ($inlineFailed) {
    exit 1
}

Write-Host "All checks passed."
