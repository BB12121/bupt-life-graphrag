param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '请先按照 README 创建 .venv 并安装依赖。'
}
if (-not $SkipBuild) {
    Push-Location (Join-Path $projectRoot 'bupt-graphrag-frontend')
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败。' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw '前端构建失败。' }
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'bupt-graphrag-frontend\dist\index.html'))) {
    throw '缺少前端构建产物，请去掉 -SkipBuild 后重试。'
}
Write-Output '打开 http://127.0.0.1:8000 使用完整应用；/docs 为接口文档。'
& $pythonPath -m uvicorn bupt_rag.api:app --host 127.0.0.1 --port 8000 --workers 1
