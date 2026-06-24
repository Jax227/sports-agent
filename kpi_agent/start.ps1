# KPI Agent — 一键启动脚本 (FastAPI + Streamlit + 公网隧道)
# 用法: powershell -ExecutionPolicy Bypass -File start.ps1

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  KPI Agent — 启动中..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 启动 FastAPI (后台)
Write-Host "[1/3] 启动 FastAPI (端口 9999)..." -ForegroundColor Yellow
$fastapiJob = Start-Job -Name "FastAPI" -ScriptBlock {
    Set-Location $using:projectDir
    uvicorn app.main:app --host 0.0.0.0 --port 9999 --log-level info
}
Write-Host "  FastAPI 已启动: http://0.0.0.0:9999" -ForegroundColor Green
Write-Host "  API 文档: http://0.0.0.0:9999/docs" -ForegroundColor Green
Write-Host ""

# 2. 启动 Streamlit (后台)
Write-Host "[2/3] 启动 Streamlit (端口 8504)..." -ForegroundColor Yellow
$streamlitJob = Start-Job -Name "Streamlit" -ScriptBlock {
    Set-Location $using:projectDir
    streamlit run app/streamlit_app.py --server.headless true
}
Write-Host "  Streamlit 已启动: http://0.0.0.0:8504" -ForegroundColor Green
Write-Host ""

# 3. 启动 Cloudflare Tunnel (后台)
Write-Host "[3/3] 启动 Cloudflare 公网隧道..." -ForegroundColor Yellow
$tunnelJob = Start-Job -Name "CloudflareTunnel" -ScriptBlock {
    cloudflared tunnel --url http://localhost:8504 2>&1
}
Write-Host "  等待隧道建立..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

# 提取公网 URL
$tunnelOutput = Receive-Job -Name "CloudflareTunnel" 2>$null
$publicUrl = ""
foreach ($line in $tunnelOutput) {
    if ($line -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
        $publicUrl = $matches[1]
        break
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  局域网访问:" -ForegroundColor White
Write-Host "    Streamlit : http://localhost:8504" -ForegroundColor Green
Write-Host "    FastAPI   : http://localhost:9999/docs" -ForegroundColor Green
Write-Host ""

if ($publicUrl) {
    Write-Host "  公网访问 (Cloudflare Tunnel):" -ForegroundColor White
    Write-Host "    $publicUrl" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  分享此链接即可让他人从公网访问！" -ForegroundColor Yellow
} else {
    Write-Host "  公网隧道: 正在建立中（约需 10 秒）..." -ForegroundColor Yellow
    Write-Host "  请稍后检查隧道日志获取 URL" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor Gray
Write-Host "  或运行 stop.ps1 停止" -ForegroundColor Gray

# 保持脚本运行，实时显示公网 URL
try {
    while ($true) {
        $newOutput = Receive-Job -Name "CloudflareTunnel" 2>$null
        foreach ($line in $newOutput) {
            if ($line -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
                $url = $matches[1]
                if ($url -ne $publicUrl) {
                    Write-Host "  公网 URL: $url" -ForegroundColor Magenta
                    $publicUrl = $url
                }
            }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    Write-Host "所有服务已停止。" -ForegroundColor Red
}
