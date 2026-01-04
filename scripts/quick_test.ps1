# Quick Test Script for FDS (Windows PowerShell)
# 快速測試腳本 - 驗證所有最新更新

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "FDS 快速測試腳本 (Windows)" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Test counter
$script:Passed = 0
$script:Failed = 0

# Function to run test
function Run-Test {
    param(
        [string]$TestName,
        [scriptblock]$TestCommand
    )

    Write-Host "▶ 測試: $TestName" -ForegroundColor Yellow

    try {
        $output = & $TestCommand 2>&1
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0 -or $null -eq $exitCode) {
            Write-Host "✓ 通過" -ForegroundColor Green
            $script:Passed++
        } else {
            Write-Host "✗ 失敗 (Exit Code: $exitCode)" -ForegroundColor Red
            Write-Host "輸出:" -ForegroundColor Gray
            $output | Select-Object -Last 10 | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
            $script:Failed++
        }
    } catch {
        Write-Host "✗ 失敗 (Exception)" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        $script:Failed++
    }

    Write-Host ""
}

# Test 1: Skeleton Extractor 單元測試
Run-Test "Skeleton Extractor 單元測試" {
    uv run pytest tests/lifecycle/test_skeleton_extractor.py -v -q
}

# Test 2: Clip Cleanup 單元測試
Run-Test "Clip Cleanup 單元測試" {
    uv run pytest tests/lifecycle/test_clip_cleanup.py -v -q
}

# Test 3: Schema 驗證器測試
Run-Test "Schema Validator 測試" {
    uv run pytest tests/lifecycle/test_schema.py -v -q
}

# Test 4: Formats 測試
Run-Test "Skeleton Formats 測試" {
    uv run pytest tests/lifecycle/test_formats.py -v -q
}

# Test 5: 真實骨架提取測試（如果測試影片存在）
if (Test-Path "tests\fixtures\videos\fall-01-cam0.mp4") {
    Write-Host "▶ 測試: 真實影片骨架提取" -ForegroundColor Yellow

    $pythonScript = @"
from pathlib import Path
from src.lifecycle.skeleton_extractor import SkeletonExtractor
from src.lifecycle.schema.validator import SkeletonValidator

try:
    extractor = SkeletonExtractor(model_path='yolo11s-pose.pt')
    output_path = Path('data/quick_test_skeleton.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    extractor.extract_and_save(
        'tests/fixtures/videos/fall-01-cam0.mp4',
        output_path,
        event_id='evt_quicktest'
    )

    validator = SkeletonValidator()
    if validator.validate_file(output_path):
        print('SUCCESS')
        exit(0)
    else:
        print('VALIDATION_FAILED')
        exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    exit(1)
"@

    try {
        $output = uv run python -c $pythonScript 2>&1
        if ($output -match "SUCCESS") {
            Write-Host "✓ 通過" -ForegroundColor Green
            $script:Passed++
        } else {
            Write-Host "✗ 失敗" -ForegroundColor Red
            Write-Host $output -ForegroundColor Gray
            $script:Failed++
        }
    } catch {
        Write-Host "✗ 失敗 (Exception)" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        $script:Failed++
    }

    Write-Host ""
} else {
    Write-Host "⊘ 跳過: 真實影片測試（測試影片不存在）" -ForegroundColor Yellow
    Write-Host ""
}

# Summary
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "測試結果總結" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "通過: $script:Passed" -ForegroundColor Green
Write-Host "失敗: $script:Failed" -ForegroundColor Red
Write-Host ""

if ($script:Failed -eq 0) {
    Write-Host "✓ 所有測試通過！" -ForegroundColor Green
    exit 0
} else {
    Write-Host "✗ 有測試失敗，請檢查錯誤訊息" -ForegroundColor Red
    exit 1
}
