/**
 * FDS Dashboard JavaScript
 */

// 自動重新整理狀態
let autoRefreshInterval = null;

/**
 * 初始化頁面
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('FDS Dashboard loaded');
    
    // 初始化自動重新整理（每 30 秒）
    if (document.querySelector('.stats-grid')) {
        startAutoRefresh(30000);
    }
});

/**
 * 開始自動重新整理
 * @param {number} interval - 重新整理間隔（毫秒）
 */
function startAutoRefresh(interval) {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(function() {
        updateStats();
    }, interval);
}

/**
 * 更新統計資訊
 */
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        // 更新統計卡片
        const statValues = document.querySelectorAll('.stat-value');
        if (statValues.length >= 4) {
            statValues[0].textContent = data.total_events;
            statValues[1].textContent = data.today_events;
            statValues[2].textContent = data.this_week_events;
            statValues[3].textContent = `${data.total_clips_size_mb.toFixed(1)} MB`;
        }
    } catch (error) {
        console.error('Failed to update stats:', error);
    }
}

/**
 * 格式化時間戳記
 * @param {number} timestamp - Unix 時間戳記
 * @returns {string} 格式化的時間字串
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-TW', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

/**
 * 格式化檔案大小
 * @param {number} bytes - 位元組數
 * @returns {string} 格式化的大小字串
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 顯示確認對話框
 * @param {string} message - 確認訊息
 * @returns {boolean} 使用者是否確認
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * 顯示訊息通知
 * @param {string} message - 訊息內容
 * @param {string} type - 訊息類型 ('success', 'error', 'info')
 */
function showNotification(message, type = 'info') {
    // 簡單的 alert 實作，可以之後改成更好的 toast
    alert(message);
}

/**
 * API 請求封裝
 * @param {string} url - API URL
 * @param {object} options - fetch 選項
 * @returns {Promise<object>} 回應資料
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request error:', error);
        throw error;
    }
}
