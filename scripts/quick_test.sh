#!/bin/bash
# Quick Test Script for FDS
# 快速測試腳本 - 驗證所有最新更新

set -e  # Exit on error

echo "======================================"
echo "FDS 快速測試腳本"
echo "======================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to run test
run_test() {
    local test_name="$1"
    local test_cmd="$2"

    echo -e "${YELLOW}▶ 測試: ${test_name}${NC}"

    if eval "$test_cmd" > /tmp/fds_test_output.log 2>&1; then
        echo -e "${GREEN}✓ 通過${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ 失敗${NC}"
        echo "錯誤日誌："
        tail -10 /tmp/fds_test_output.log
        ((FAILED++))
    fi
    echo ""
}

# Test 1: Skeleton Extractor 單元測試
run_test "Skeleton Extractor 單元測試" \
    "uv run pytest tests/lifecycle/test_skeleton_extractor.py -v -q"

# Test 2: Clip Cleanup 單元測試
run_test "Clip Cleanup 單元測試" \
    "uv run pytest tests/lifecycle/test_clip_cleanup.py -v -q"

# Test 3: Schema 驗證器測試
run_test "Schema Validator 測試" \
    "uv run pytest tests/lifecycle/test_schema.py -v -q"

# Test 4: Formats 測試
run_test "Skeleton Formats 測試" \
    "uv run pytest tests/lifecycle/test_formats.py -v -q"

# Test 5: Docker 配置驗證
run_test "Docker Compose 配置驗證" \
    "docker compose config --dry-run > /dev/null 2>&1"

# Test 6: 真實骨架提取測試（如果測試影片存在）
if [ -f "tests/fixtures/videos/fall-01-cam0.mp4" ]; then
    echo -e "${YELLOW}▶ 測試: 真實影片骨架提取${NC}"

    uv run python3 -c "
from pathlib import Path
from src.lifecycle.skeleton_extractor import SkeletonExtractor
from src.lifecycle.schema.validator import SkeletonValidator

try:
    extractor = SkeletonExtractor(model_path='yolov8n-pose.pt')
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
" > /tmp/fds_skeleton_test.log 2>&1

    if grep -q "SUCCESS" /tmp/fds_skeleton_test.log; then
        echo -e "${GREEN}✓ 通過${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ 失敗${NC}"
        cat /tmp/fds_skeleton_test.log
        ((FAILED++))
    fi
    echo ""
else
    echo -e "${YELLOW}⊘ 跳過: 真實影片測試（測試影片不存在）${NC}"
    echo ""
fi

# Summary
echo "======================================"
echo "測試結果總結"
echo "======================================"
echo -e "${GREEN}通過: ${PASSED}${NC}"
echo -e "${RED}失敗: ${FAILED}${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有測試通過！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有測試失敗，請檢查錯誤日誌${NC}"
    exit 1
fi
