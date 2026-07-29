# MHWilds配装搜索器 - 推送到GitHub脚本
# 运行方式：右键选择"使用 PowerShell 运行"

$wsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $wsDir

Write-Host "=== MHWilds配装搜索器 Git推送 ===" -ForegroundColor Cyan
Write-Host ""

# 检查提交状态
$commitCount = git rev-list --count HEAD 2>$null
if ($commitCount -eq 0) {
    Write-Host "错误：没有提交记录。请先运行搜索器生成结果。" -ForegroundColor Red
    exit 1
}

Write-Host "本地提交数: $commitCount" -ForegroundColor Green
Write-Host "远程仓库: $(git remote get-url origin)" -ForegroundColor Green
Write-Host ""

# 提示用户输入PAT
Write-Host "GitHub已不再支持密码认证，需要使用Personal Access Token (PAT)。" -ForegroundColor Yellow
Write-Host "如果你还没有PAT，请按以下步骤创建：" -ForegroundColor Yellow
Write-Host "  1. 打开 https://github.com/settings/tokens" -ForegroundColor Gray
Write-Host "  2. 点击 'Generate new token (classic)'" -ForegroundColor Gray
Write-Host "  3. 勾选 'repo' 权限" -ForegroundColor Gray
Write-Host "  4. 生成并复制token（只显示一次）" -ForegroundColor Gray
Write-Host ""

# 使用安全输入框获取PAT
$PAT = Read-Host -AsSecureString "请输入你的GitHub Personal Access Token"
$PATPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($PAT))

if ([string]::IsNullOrWhiteSpace($PATPlain)) {
    Write-Host "未输入token，取消推送。" -ForegroundColor Red
    exit 1
}

# 配置临时凭证（仅本次推送）
$remoteUrl = "https://ppz12138:$PATPlain@github.com/ppz12138/-.git"
git remote set-url origin $remoteUrl

Write-Host ""
Write-Host "正在推送到GitHub..." -ForegroundColor Cyan

# 推送
try {
    git push -u origin master 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "推送成功！" -ForegroundColor Green
        Write-Host "仓库地址: https://github.com/ppz12138/-" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "推送失败，请检查token是否正确。" -ForegroundColor Red
    }
} finally {
    # 恢复原始远程地址（清除凭证）
    git remote set-url origin "https://github.com/ppz12138/-.git"
    # 清除变量
    $PATPlain = $null
    $PAT = $null
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
