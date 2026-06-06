# Kill all ngrok processes
Write-Host "🛑 Killing all ngrok processes..." -ForegroundColor Yellow
Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Verify ngrok is killed
if (Get-Process ngrok -ErrorAction SilentlyContinue) {
    Write-Host "❌ ngrok still running, trying harder..." -ForegroundColor Red
    Get-Process ngrok | Stop-Process -Force -Confirm:$false
    Start-Sleep -Seconds 3
}

Write-Host "✅ All ngrok processes killed" -ForegroundColor Green

# Start ngrok with pooling mode enabled (if previous endpoint still online)
Write-Host "🚀 Starting ngrok on port 8000 with pooling mode..." -ForegroundColor Cyan
Start-Process -NoNewWindow ngrok http 8000 --pooling-enabled

Start-Sleep -Seconds 5

# Get ngrok URL and show it
$ngrokUrl = (Invoke-WebRequest -Uri "http://localhost:4040/api/tunnels" -ErrorAction SilentlyContinue | ConvertFrom-Json).tunnels[0].public_url -replace 'http://', 'https://'

Write-Host "✅ ngrok started successfully!" -ForegroundColor Green
if ($ngrokUrl) {
    Write-Host "📍 Public URL: $ngrokUrl" -ForegroundColor Cyan
    Write-Host "📝 Update TELEGRAM_WEBHOOK_URL in .env to: $ngrokUrl/api/webhook/telegram" -ForegroundColor Cyan
}

Write-Host "`n🤖 Now restart your FastAPI server with: python backend\app\main.py" -ForegroundColor Yellow
