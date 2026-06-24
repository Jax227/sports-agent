# 停止所有 KPI Agent 服务
Write-Host "正在停止 KPI Agent 服务..." -ForegroundColor Yellow
Get-Job | Stop-Job
Get-Job | Remove-Job
# 也停止可能由其他方式启动的进程
Get-Process -Name "python","streamlit","cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "已停止。" -ForegroundColor Green
