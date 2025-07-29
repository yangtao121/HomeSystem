// ArXiv论文数据可视化 - 前端交互脚本

document.addEventListener('DOMContentLoaded', function() {
    // 初始化所有功能
    initSearchFunctionality();
    initDataVisualization();
    initTooltips();
    initResponsiveFeatures();
});

/**
 * 搜索功能初始化
 */
function initSearchFunctionality() {
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('searchInput');
    
    if (searchForm && searchInput) {
        // 实时搜索建议（可选）
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                // 可以在这里添加搜索建议功能
                console.log('搜索建议:', this.value);
            }, 300);
        });
        
        // 搜索表单提交处理
        searchForm.addEventListener('submit', function(e) {
            const query = searchInput.value.trim();
            if (!query) {
                e.preventDefault();
                showAlert('请输入搜索关键词', 'warning');
            }
        });
    }
    
    // 快速过滤按钮
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filterType = this.dataset.filter;
            const filterValue = this.dataset.value;
            applyFilter(filterType, filterValue);
        });
    });
}

/**
 * 数据可视化初始化
 */
function initDataVisualization() {
    // 状态分布饼图
    const statusChartCtx = document.getElementById('statusChart');
    if (statusChartCtx && typeof Chart !== 'undefined') {
        createStatusChart(statusChartCtx);
    }
    
    // 分类分布条形图
    const categoryChartCtx = document.getElementById('categoryChart');
    if (categoryChartCtx && typeof Chart !== 'undefined') {
        createCategoryChart(categoryChartCtx);
    }
    
    // 时间趋势图
    const trendChartCtx = document.getElementById('trendChart');
    if (trendChartCtx && typeof Chart !== 'undefined') {
        createTrendChart(trendChartCtx);
    }
}

/**
 * 创建状态分布饼图
 */
function createStatusChart(ctx) {
    const statusData = getStatusData();
    if (!statusData) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: statusData.labels,
            datasets: [{
                data: statusData.values,
                backgroundColor: [
                    '#27ae60', // completed - 绿色
                    '#f39c12', // pending - 橙色
                    '#e74c3c'  // failed - 红色
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * 创建分类分布条形图
 */
function createCategoryChart(ctx) {
    const categoryData = getCategoryData();
    if (!categoryData) return;
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: categoryData.labels,
            datasets: [{
                label: '论文数量',
                data: categoryData.values,
                backgroundColor: 'rgba(52, 152, 219, 0.8)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 0
                    }
                }
            }
        }
    });
}

/**
 * 创建时间趋势图
 */
function createTrendChart(ctx) {
    const trendData = getTrendData();
    if (!trendData) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendData.labels,
            datasets: [{
                label: '新增论文',
                data: trendData.values,
                borderColor: 'rgba(52, 152, 219, 1)',
                backgroundColor: 'rgba(52, 152, 219, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

/**
 * 获取状态数据（从页面数据中提取）
 */
function getStatusData() {
    const statusElement = document.getElementById('statusData');
    if (!statusElement) return null;
    
    try {
        return JSON.parse(statusElement.textContent);
    } catch (e) {
        console.error('状态数据解析失败:', e);
        return null;
    }
}

/**
 * 获取分类数据
 */
function getCategoryData() {
    const categoryElement = document.getElementById('categoryData');
    if (!categoryElement) return null;
    
    try {
        return JSON.parse(categoryElement.textContent);
    } catch (e) {
        console.error('分类数据解析失败:', e);
        return null;
    }
}

/**
 * 获取趋势数据
 */
function getTrendData() {
    const trendElement = document.getElementById('trendData');
    if (!trendElement) return null;
    
    try {
        return JSON.parse(trendElement.textContent);
    } catch (e) {
        console.error('趋势数据解析失败:', e);
        return null;
    }
}

/**
 * 应用过滤器
 */
function applyFilter(filterType, filterValue) {
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.set(filterType, filterValue);
    currentUrl.searchParams.delete('page'); // 重置分页
    window.location.href = currentUrl.toString();
}

/**
 * 清除所有过滤器
 */
function clearFilters() {
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.delete('q');
    currentUrl.searchParams.delete('category');
    currentUrl.searchParams.delete('status');
    currentUrl.searchParams.delete('page');
    window.location.href = currentUrl.toString();
}

/**
 * 初始化工具提示
 */
function initTooltips() {
    // 如果Bootstrap可用，初始化工具提示
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

/**
 * 初始化响应式功能
 */
function initResponsiveFeatures() {
    // 移动端菜单切换
    const mobileMenuToggle = document.querySelector('.navbar-toggler');
    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', function() {
            const navbarCollapse = document.querySelector('.navbar-collapse');
            if (navbarCollapse) {
                navbarCollapse.classList.toggle('show');
            }
        });
    }
    
    // 响应式表格
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        if (!table.parentElement.classList.contains('table-responsive')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'table-responsive';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }
    });
}

/**
 * 显示警告消息
 */
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    if (!alertContainer) {
        console.warn('未找到警告容器');
        return;
    }
    
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${type} alert-dismissible fade show`;
    alertElement.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alertElement);
    
    // 3秒后自动消失
    setTimeout(() => {
        if (alertElement.parentNode) {
            alertElement.remove();
        }
    }, 3000);
}

/**
 * 复制文本到剪贴板
 */
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert('已复制到剪贴板', 'success');
        }).catch(err => {
            console.error('复制失败:', err);
            showAlert('复制失败', 'error');
        });
    } else {
        // 降级方案
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showAlert('已复制到剪贴板', 'success');
        } catch (err) {
            console.error('复制失败:', err);
            showAlert('复制失败', 'error');
        }
        document.body.removeChild(textArea);
    }
}

/**
 * 导出数据功能
 */
function exportData(format = 'json') {
    const currentParams = new URLSearchParams(window.location.search);
    currentParams.set('export', format);
    
    const exportUrl = `/api/export?${currentParams.toString()}`;
    
    // 创建临时链接下载
    const link = document.createElement('a');
    link.href = exportUrl;
    link.download = `arxiv_papers_${new Date().toISOString().split('T')[0]}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * 刷新数据
 */
function refreshData() {
    // 显示加载状态
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<span class="loading"></span> 刷新中...';
        refreshBtn.disabled = true;
    }
    
    // 清除缓存并重新加载
    fetch('/api/refresh', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('数据已刷新', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showAlert('刷新失败: ' + data.error, 'error');
            }
        })
        .catch(err => {
            console.error('刷新失败:', err);
            showAlert('刷新失败', 'error');
        })
        .finally(() => {
            if (refreshBtn) {
                refreshBtn.innerHTML = '刷新数据';
                refreshBtn.disabled = false;
            }
        });
}

// 键盘快捷键支持
document.addEventListener('keydown', function(e) {
    // Ctrl+K 或 Cmd+K 聚焦搜索框
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // ESC 键清除搜索
    if (e.key === 'Escape') {
        const searchInput = document.getElementById('searchInput');
        if (searchInput && document.activeElement === searchInput) {
            searchInput.value = '';
        }
    }
});

// 页面性能监控
window.addEventListener('load', function() {
    if (window.performance) {
        const loadTime = window.performance.timing.loadEventEnd - window.performance.timing.navigationStart;
        console.log(`页面加载时间: ${loadTime}ms`);
        
        // 如果加载时间过长，显示提示
        if (loadTime > 3000) {
            showAlert('页面加载较慢，建议检查网络连接', 'warning');
        }
    }
});

// 导出给全局使用
window.ExplorePaperData = {
    applyFilter,
    clearFilters,
    showAlert,
    copyToClipboard,
    exportData,
    refreshData
};