# Quick Start Script for SMI DSS React Dashboard

Write-Host "🚀 Starting SMI Decision Support System with React Dashboard..." -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
$dockerStatus = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker is running" -ForegroundColor Green
Write-Host ""

# Check if .env exists
if (-Not (Test-Path ".env")) {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✅ .env file created" -ForegroundColor Green
    Write-Host ""
}

# Stop existing containers
Write-Host "🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host "✅ Containers stopped" -ForegroundColor Green
Write-Host ""

# Build and start containers
Write-Host "🔨 Building containers (this may take 10-15 minutes on first run)..." -ForegroundColor Yellow
docker-compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Build completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    Write-Host ""
    Write-Host "🎉 SMI DSS is ready!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Access the dashboard at:" -ForegroundColor Cyan
    Write-Host "   🌐 React Dashboard: http://localhost:3000" -ForegroundColor White
    Write-Host "   🔧 Backend API:     http://localhost:8000/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "📋 Available pages:" -ForegroundColor Cyan
    Write-Host "   • Dashboard Overview" -ForegroundColor White
    Write-Host "   • Data Overview" -ForegroundColor White
    Write-Host "   • What-If Scenarios (11 scenarios, 5 groups)" -ForegroundColor White
    Write-Host "   • Sensitivity Analysis (7 parameters)" -ForegroundColor White
    Write-Host "   • Optimization Results" -ForegroundColor White
    Write-Host "   • Scenario Comparison" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 Quick commands:" -ForegroundColor Cyan
    Write-Host "   View logs:    docker-compose logs -f" -ForegroundColor White
    Write-Host "   Stop system:  docker-compose down" -ForegroundColor White
    Write-Host "   Restart:      docker-compose restart" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ Build failed! Check the error messages above." -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Troubleshooting:" -ForegroundColor Yellow
    Write-Host "   1. Clean Docker cache:  docker system prune -f" -ForegroundColor White
    Write-Host "   2. Rebuild from scratch: docker-compose build --no-cache" -ForegroundColor White
    Write-Host "   3. Check logs:          docker-compose logs" -ForegroundColor White
    Write-Host ""
    exit 1
}
