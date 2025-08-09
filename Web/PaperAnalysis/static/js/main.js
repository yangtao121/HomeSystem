// PaperAnalysis - 统一前端交互脚本
// 整合了PaperGather和ExplorePaperData的前端功能

document.addEventListener('DOMContentLoaded', function() {
    // 初始化所有功能
    initSearchFunctionality();
    initDataVisualization();
    initTooltips();
    initResponsiveFeatures();
    initAnalysisConfigModal();
    initBootstrapSelect();
    
    // 全局错误处理
    window.addEventListener('error', function(e) {
        console.error('应用错误:', e.error);
        showAlert('应用出现错误，请刷新页面重试', 'danger');
    });
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
 * 自动提交筛选表单（用于多选框变化时）
 */
function autoSubmitFilters() {
    // 延迟提交，避免用户快速选择时频繁提交
    clearTimeout(window.filterTimeout);
    window.filterTimeout = setTimeout(() => {
        const form = document.getElementById('searchForm');
        if (form) {
            // 移除page参数以重置分页
            const pageInput = form.querySelector('input[name="page"]');
            if (pageInput) {
                pageInput.remove();
            }
            
            // 提交表单
            form.submit();
        }
    }, 500); // 500ms延迟
}

/**
 * 清除所有过滤器
 */
function clearFilters() {
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.delete('q');
    currentUrl.searchParams.delete('category');
    currentUrl.searchParams.delete('status');
    currentUrl.searchParams.delete('task_name');
    currentUrl.searchParams.delete('task_id');
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
 * 初始化Bootstrap Select组件
 */
function initBootstrapSelect() {
    // 检查Bootstrap Select是否可用
    if (typeof $.fn.selectpicker !== 'undefined') {
        // 初始化所有selectpicker
        $('.selectpicker').selectpicker({
            style: 'btn-outline-secondary',
            size: 8,
            liveSearch: true,
            actionsBox: true,
            showTick: true,
            dropupAuto: false
        });
        
        // 监听选择变化事件
        $('.selectpicker').on('changed.bs.select', function(e, clickedIndex, isSelected, previousValue) {
            // 确保触发我们的自动提交函数
            if (typeof autoSubmitFilters === 'function') {
                autoSubmitFilters();
            }
        });
    } else {
        console.warn('Bootstrap Select 未加载，使用原生select');
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
        try {
            // 使用现代的Navigation Timing API
            const navigationEntries = performance.getEntriesByType('navigation');
            if (navigationEntries.length > 0) {
                const loadTime = Math.round(navigationEntries[0].loadEventEnd - navigationEntries[0].fetchStart);
                console.log(`页面加载时间: ${loadTime}ms`);
                
                // 如果加载时间过长，显示提示
                if (loadTime > 3000) {
                    showAlert('页面加载较慢，建议检查网络连接', 'warning');
                }
            } else {
                // 降级方案：使用performance.now()
                const loadTime = Math.round(performance.now());
                console.log(`页面加载时间: ${loadTime}ms`);
            }
        } catch (error) {
            console.log('性能监控初始化失败:', error.message);
        }
    }
});

/**
 * 相关度编辑功能
 */

// 在列表页面快速编辑相关度
function editRelevanceQuick(arxivId) {
    // 复用详情页的编辑功能，但使用简化的模态框
    if (typeof editRelevance === 'function') {
        editRelevance(arxivId);
    } else {
        // 如果没有详情页的函数，创建简化版本
        createQuickRelevanceModal(arxivId);
    }
}

// 创建快速相关度编辑模态框
function createQuickRelevanceModal(arxivId) {
    // 检查是否已存在模态框
    let modal = document.getElementById('quickRelevanceModal');
    if (!modal) {
        // 创建模态框HTML
        const modalHTML = `
        <div class="modal fade" id="quickRelevanceModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-star"></i> 快速编辑相关度
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <input type="hidden" id="quick-edit-arxiv-id">
                        
                        <!-- 评分输入 -->
                        <div class="mb-3">
                            <label for="quick-relevance-score" class="form-label">相关度评分 (0.00-1.00)</label>
                            <input type="number" class="form-control" id="quick-relevance-score"
                                   min="0" max="1" step="0.01" placeholder="请输入0.00-1.00之间的数值">
                            <div class="mt-2">
                                <span id="quick-score-preview" class="fs-6"></span>
                            </div>
                        </div>
                        
                        <!-- 快捷评分按钮 -->
                        <div class="mb-3">
                            <label class="form-label">快捷评分</label>
                            <div class="btn-group d-block" role="group">
                                <button type="button" class="btn btn-success btn-sm me-1" data-quick-score="0.9">
                                    高相关 (0.9)
                                </button>
                                <button type="button" class="btn btn-warning btn-sm me-1" data-quick-score="0.7">
                                    中相关 (0.7)
                                </button>
                                <button type="button" class="btn btn-info btn-sm me-1" data-quick-score="0.5">
                                    一般 (0.5)
                                </button>
                                <button type="button" class="btn btn-secondary btn-sm me-1" data-quick-score="0.3">
                                    低相关 (0.3)
                                </button>
                                <button type="button" class="btn btn-danger btn-sm" data-quick-score="0.1">
                                    不相关 (0.1)
                                </button>
                            </div>
                        </div>
                        
                        <!-- 理由输入 -->
                        <div class="mb-3">
                            <label for="quick-relevance-justification" class="form-label">相关度理由</label>
                            <textarea class="form-control" id="quick-relevance-justification" 
                                      rows="4" maxlength="5000"
                                      placeholder="请简要描述该论文与研究需求的相关性..."></textarea>
                            <div class="form-text">
                                <span id="quick-char-count">0</span>/5000 字符
                            </div>
                        </div>
                        
                        <!-- 保存状态 -->
                        <div class="alert alert-info d-none" id="quick-save-status">
                            <span id="quick-save-message"></span>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            <i class="bi bi-x-circle"></i> 取消
                        </button>
                        <button type="button" class="btn btn-primary" id="quick-save-relevance-btn">
                            <i class="bi bi-check-circle"></i> 保存
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
        
        // 添加到页面
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        modal = document.getElementById('quickRelevanceModal');
        
        // 绑定事件
        bindQuickRelevanceEvents();
    }
    
    // 设置当前编辑的论文ID
    document.getElementById('quick-edit-arxiv-id').value = arxivId;
    
    // 清空表单
    document.getElementById('quick-relevance-score').value = '';
    document.getElementById('quick-relevance-justification').value = '';
    updateQuickScorePreview();
    updateQuickCharCount();
    
    // 显示模态框
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// 绑定快速编辑相关度的事件
function bindQuickRelevanceEvents() {
    // 快捷评分按钮
    document.querySelectorAll('[data-quick-score]').forEach(btn => {
        btn.addEventListener('click', function() {
            const score = this.dataset.quickScore;
            document.getElementById('quick-relevance-score').value = score;
            updateQuickScorePreview();
        });
    });
    
    // 评分输入变化
    document.getElementById('quick-relevance-score').addEventListener('input', updateQuickScorePreview);
    
    // 理由输入变化
    document.getElementById('quick-relevance-justification').addEventListener('input', updateQuickCharCount);
    
    // 保存按钮
    document.getElementById('quick-save-relevance-btn').addEventListener('click', saveQuickRelevance);
}

// 更新快速编辑的评分预览
function updateQuickScorePreview() {
    const score = parseFloat(document.getElementById('quick-relevance-score').value);
    const preview = document.getElementById('quick-score-preview');
    
    if (isNaN(score) || score < 0 || score > 1) {
        preview.innerHTML = '<span class="text-muted">☆☆☆☆☆</span>';
        return;
    }
    
    const starsCount = Math.round(score * 5);
    const filledStars = '★'.repeat(starsCount);
    const emptyStars = '☆'.repeat(5 - starsCount);
    
    let colorClass;
    if (score >= 0.8) colorClass = 'text-success';
    else if (score >= 0.5) colorClass = 'text-warning';
    else colorClass = 'text-danger';
    
    preview.innerHTML = `<span class="${colorClass}">${filledStars}${emptyStars}</span> (${score.toFixed(2)})`;
}

// 更新快速编辑的字符计数
function updateQuickCharCount() {
    const text = document.getElementById('quick-relevance-justification').value;
    document.getElementById('quick-char-count').textContent = text.length;
}

// 保存快速编辑的相关度
function saveQuickRelevance() {
    const arxivId = document.getElementById('quick-edit-arxiv-id').value;
    const score = document.getElementById('quick-relevance-score').value;
    const justification = document.getElementById('quick-relevance-justification').value.trim();
    
    // 验证输入
    if (!score && !justification) {
        showQuickSaveStatus('error', '请至少填写评分或理由');
        return;
    }
    
    if (score && (parseFloat(score) < 0 || parseFloat(score) > 1)) {
        showQuickSaveStatus('error', '评分必须在0-1之间');
        return;
    }
    
    const saveBtn = document.getElementById('quick-save-relevance-btn');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> 保存中...';
    saveBtn.disabled = true;
    
    // 准备数据
    const data = { arxiv_id: arxivId };
    if (score) data.relevance_score = parseFloat(score);
    if (justification) data.relevance_justification = justification;
    
    // 发送请求
    fetch('/api/update_relevance', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showQuickSaveStatus('success', '保存成功！页面将刷新...');
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showQuickSaveStatus('error', data.error || '保存失败');
        }
    })
    .catch(error => {
        console.error('保存失败:', error);
        showQuickSaveStatus('error', '网络错误，请稍后重试');
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// 显示快速编辑的保存状态
function showQuickSaveStatus(type, message) {
    const statusDiv = document.getElementById('quick-save-status');
    const messageSpan = document.getElementById('quick-save-message');
    
    statusDiv.classList.remove('alert-info', 'alert-success', 'alert-danger', 'd-none');
    
    if (type === 'success') {
        statusDiv.classList.add('alert-success');
        messageSpan.innerHTML = `<i class="bi bi-check-circle"></i> ${message}`;
    } else if (type === 'error') {
        statusDiv.classList.add('alert-danger');
        messageSpan.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;
    } else {
        statusDiv.classList.add('alert-info');
        messageSpan.innerHTML = `<i class="bi bi-info-circle"></i> ${message}`;
    }
}

// 批量编辑相关度
function batchEditRelevance() {
    const selectedPapers = getSelectedPapers();
    if (selectedPapers.length === 0) {
        showAlert('请先选择要编辑的论文', 'warning');
        return;
    }
    
    // 创建批量编辑模态框
    createBatchRelevanceModal(selectedPapers);
}

// 创建批量相关度编辑模态框
function createBatchRelevanceModal(selectedPapers) {
    // 检查是否已存在模态框
    let modal = document.getElementById('batchRelevanceModal');
    if (!modal) {
        const modalHTML = `
        <div class="modal fade" id="batchRelevanceModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-star"></i> 批量编辑相关度
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-info">
                            <i class="bi bi-info-circle"></i>
                            已选择 <strong id="batch-paper-count">0</strong> 篇论文进行批量编辑
                        </div>
                        
                        <!-- 评分设置 -->
                        <div class="mb-3">
                            <label class="form-label">批量设置评分</label>
                            <div class="row">
                                <div class="col-md-6">
                                    <input type="number" class="form-control" id="batch-relevance-score"
                                           min="0" max="1" step="0.01" placeholder="请输入0.00-1.00之间的数值">
                                </div>
                                <div class="col-md-6">
                                    <span id="batch-score-preview" class="fs-6"></span>
                                </div>
                            </div>
                            <div class="mt-2">
                                <button type="button" class="btn btn-success btn-sm me-1" data-batch-score="0.9">高相关</button>
                                <button type="button" class="btn btn-warning btn-sm me-1" data-batch-score="0.7">中相关</button>
                                <button type="button" class="btn btn-info btn-sm me-1" data-batch-score="0.5">一般</button>
                                <button type="button" class="btn btn-secondary btn-sm me-1" data-batch-score="0.3">低相关</button>
                                <button type="button" class="btn btn-danger btn-sm" data-batch-score="0.1">不相关</button>
                            </div>
                        </div>
                        
                        <!-- 理由设置 -->
                        <div class="mb-3">
                            <label class="form-label">批量设置理由</label>
                            <textarea class="form-control" id="batch-relevance-justification" 
                                      rows="4" maxlength="5000"
                                      placeholder="批量设置的理由将应用于所有选中的论文..."></textarea>
                            <div class="form-text">
                                <span id="batch-char-count">0</span>/5000 字符
                            </div>
                        </div>
                        
                        <!-- 保存状态 -->
                        <div class="alert alert-info d-none" id="batch-save-status">
                            <span id="batch-save-message"></span>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            <i class="bi bi-x-circle"></i> 取消
                        </button>
                        <button type="button" class="btn btn-primary" id="batch-save-relevance-btn">
                            <i class="bi bi-check-circle"></i> 批量保存
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        modal = document.getElementById('batchRelevanceModal');
        bindBatchRelevanceEvents();
    }
    
    // 更新选中论文数量
    document.getElementById('batch-paper-count').textContent = selectedPapers.length;
    
    // 显示模态框
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// 绑定批量编辑相关度的事件
function bindBatchRelevanceEvents() {
    // 快捷评分按钮
    document.querySelectorAll('[data-batch-score]').forEach(btn => {
        btn.addEventListener('click', function() {
            const score = this.dataset.batchScore;
            document.getElementById('batch-relevance-score').value = score;
            updateBatchScorePreview();
        });
    });
    
    // 评分输入变化
    document.getElementById('batch-relevance-score').addEventListener('input', updateBatchScorePreview);
    
    // 理由输入变化
    document.getElementById('batch-relevance-justification').addEventListener('input', updateBatchCharCount);
    
    // 批量保存按钮
    document.getElementById('batch-save-relevance-btn').addEventListener('click', saveBatchRelevance);
}

// 更新批量编辑的评分预览
function updateBatchScorePreview() {
    const score = parseFloat(document.getElementById('batch-relevance-score').value);
    const preview = document.getElementById('batch-score-preview');
    
    if (isNaN(score) || score < 0 || score > 1) {
        preview.innerHTML = '<span class="text-muted">☆☆☆☆☆</span>';
        return;
    }
    
    const starsCount = Math.round(score * 5);
    const filledStars = '★'.repeat(starsCount);
    const emptyStars = '☆'.repeat(5 - starsCount);
    
    let colorClass;
    if (score >= 0.8) colorClass = 'text-success';
    else if (score >= 0.5) colorClass = 'text-warning';
    else colorClass = 'text-danger';
    
    preview.innerHTML = `<span class="${colorClass}">${filledStars}${emptyStars}</span> (${score.toFixed(2)})`;
}

// 更新批量编辑的字符计数
function updateBatchCharCount() {
    const text = document.getElementById('batch-relevance-justification').value;
    document.getElementById('batch-char-count').textContent = text.length;
}

// 保存批量相关度编辑
function saveBatchRelevance() {
    const selectedPapers = getSelectedPapers();
    const score = document.getElementById('batch-relevance-score').value;
    const justification = document.getElementById('batch-relevance-justification').value.trim();
    
    if (!score && !justification) {
        showBatchSaveStatus('error', '请至少填写评分或理由');
        return;
    }
    
    if (score && (parseFloat(score) < 0 || parseFloat(score) > 1)) {
        showBatchSaveStatus('error', '评分必须在0-1之间');
        return;
    }
    
    const saveBtn = document.getElementById('batch-save-relevance-btn');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> 保存中...';
    saveBtn.disabled = true;
    
    // 准备批量保存的Promise数组
    const promises = selectedPapers.map(arxivId => {
        const data = { arxiv_id: arxivId };
        if (score) data.relevance_score = parseFloat(score);
        if (justification) data.relevance_justification = justification;
        
        return fetch('/api/update_relevance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).then(response => response.json());
    });
    
    // 执行批量保存
    Promise.all(promises)
        .then(results => {
            const successful = results.filter(result => result.success).length;
            const failed = results.length - successful;
            
            if (failed === 0) {
                showBatchSaveStatus('success', `批量保存成功！已更新 ${successful} 篇论文，页面将刷新...`);
                setTimeout(() => location.reload(), 2000);
            } else {
                showBatchSaveStatus('warning', `部分保存成功：${successful} 成功，${failed} 失败`);
            }
        })
        .catch(error => {
            console.error('批量保存失败:', error);
            showBatchSaveStatus('error', '批量保存失败，请稍后重试');
        })
        .finally(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = false;
        });
}

// 显示批量保存状态
function showBatchSaveStatus(type, message) {
    const statusDiv = document.getElementById('batch-save-status');
    const messageSpan = document.getElementById('batch-save-message');
    
    statusDiv.classList.remove('alert-info', 'alert-success', 'alert-warning', 'alert-danger', 'd-none');
    
    if (type === 'success') {
        statusDiv.classList.add('alert-success');
        messageSpan.innerHTML = `<i class="bi bi-check-circle"></i> ${message}`;
    } else if (type === 'warning') {
        statusDiv.classList.add('alert-warning');
        messageSpan.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;
    } else if (type === 'error') {
        statusDiv.classList.add('alert-danger');
        messageSpan.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;
    } else {
        statusDiv.classList.add('alert-info');
        messageSpan.innerHTML = `<i class="bi bi-info-circle"></i> ${message}`;
    }
}

// 获取选中的论文ID列表
function getSelectedPapers() {
    const checkboxes = document.querySelectorAll('.paper-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.dataset.arxivId);
}

// ========== 论文迁移功能 ==========

// 全局变量存储任务列表和当前状态
let availableTasks = [];
let filteredTasks = [];
let currentMigrationArxivId = null;

// 显示单个论文迁移模态框
function showMigrationModal(arxivId, paperTitle) {
    currentMigrationArxivId = arxivId;
    document.getElementById('migrationPaperArxivId').value = arxivId;
    document.getElementById('migrationPaperTitle').textContent = paperTitle;
    
    // 清空搜索框和选择
    document.getElementById('taskSearchInput').value = '';
    clearTaskSelection();
    
    // 加载任务列表
    loadTasksForMigration('taskListContainer');
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('migrationModal'));
    modal.show();
}

// 显示批量迁移模态框
function showBatchMigrationModal() {
    const selectedPapers = getSelectedPapers();
    if (selectedPapers.length === 0) {
        showAlert('请先选择要迁移的论文', 'warning');
        return;
    }
    
    document.getElementById('batchMigrationPaperCount').textContent = selectedPapers.length;
    document.getElementById('batchTaskSearchInput').value = '';
    clearBatchTaskSelection();
    
    // 加载任务列表
    loadTasksForMigration('batchTaskListContainer');
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('batchMigrationModal'));
    modal.show();
}

// 加载可用任务列表
function loadTasksForMigration(containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">加载中...</span>
            </div>
            <p class="mt-2">正在加载任务列表...</p>
        </div>
    `;
    
    fetch('/api/tasks/available_for_migration')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                availableTasks = data.data.tasks || [];
                filteredTasks = [...availableTasks];
                renderTaskList(containerId);
            } else {
                container.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i>
                        加载任务列表失败: ${data.error}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('加载任务列表失败:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    网络错误，请稍后重试
                </div>
            `;
        });
}

// 渲染任务列表
function renderTaskList(containerId) {
    const container = document.getElementById(containerId);
    
    if (filteredTasks.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted">
                <i class="bi bi-inbox"></i>
                <p class="mt-2">没有找到可用的任务</p>
            </div>
        `;
        return;
    }
    
    const isBatch = containerId === 'batchTaskListContainer';
    const taskItems = filteredTasks.map(task => {
        const categories = task.top_categories ? task.top_categories.slice(0, 2).join(', ') : '无分类';
        const statusCounts = `完成: ${task.completed_count}, 待处理: ${task.pending_count}, 失败: ${task.failed_count}`;
        
        return `
            <div class="card mb-2 task-item" data-task-name="${task.task_name}" data-task-id="${task.task_id || ''}" 
                 style="cursor: pointer;" onclick="selectTask(this, ${isBatch})">
                <div class="card-body py-2">
                    <div class="row align-items-center">
                        <div class="col-md-8">
                            <h6 class="mb-1">${task.task_name}</h6>
                            <small class="text-muted">
                                <i class="bi bi-files"></i> ${task.paper_count} 篇论文 |
                                <i class="bi bi-tag"></i> ${categories} |
                                <i class="bi bi-clock"></i> ${new Date(task.last_created).toLocaleDateString()}
                            </small>
                        </div>
                        <div class="col-md-4 text-end">
                            <small class="text-muted">${statusCounts}</small>
                            ${task.task_id ? `<br><small class="text-info">ID: ${task.task_id}</small>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = taskItems;
}

// 选择任务
function selectTask(element, isBatch = false) {
    const taskName = element.getAttribute('data-task-name');
    const taskId = element.getAttribute('data-task-id');
    const paperCount = filteredTasks.find(t => t.task_name === taskName)?.paper_count || 0;
    
    if (isBatch) {
        // 清除之前的选择
        document.querySelectorAll('#batchTaskListContainer .task-item').forEach(item => {
            item.classList.remove('border-success', 'bg-light');
        });
        
        // 高亮当前选择
        element.classList.add('border-success', 'bg-light');
        
        // 更新选择信息
        document.getElementById('batchSelectedTaskName').textContent = taskName;
        document.getElementById('batchSelectedTaskPaperCount').textContent = paperCount;
        document.getElementById('batchSelectedTaskIdForMigration').value = taskId;
        document.getElementById('batchSelectedTaskInfo').classList.remove('d-none');
        
        // 启用按钮
        document.getElementById('previewBatchMigrationBtn').disabled = false;
        document.getElementById('confirmBatchMigrationBtn').disabled = false;
    } else {
        // 清除之前的选择
        document.querySelectorAll('#taskListContainer .task-item').forEach(item => {
            item.classList.remove('border-success', 'bg-light');
        });
        
        // 高亮当前选择
        element.classList.add('border-success', 'bg-light');
        
        // 更新选择信息
        document.getElementById('selectedTaskName').textContent = taskName;
        document.getElementById('selectedTaskPaperCount').textContent = paperCount;
        document.getElementById('selectedTaskIdForMigration').value = taskId;
        document.getElementById('selectedTaskInfo').classList.remove('d-none');
        
        // 启用确认按钮
        document.getElementById('confirmMigrationBtn').disabled = false;
    }
}

// 过滤任务列表
function filterTasks() {
    const searchTerm = document.getElementById('taskSearchInput').value.toLowerCase().trim();
    filteredTasks = availableTasks.filter(task => 
        task.task_name.toLowerCase().includes(searchTerm) ||
        (task.task_id && task.task_id.toLowerCase().includes(searchTerm)) ||
        (task.top_categories && task.top_categories.some(cat => cat.toLowerCase().includes(searchTerm)))
    );
    renderTaskList('taskListContainer');
    clearTaskSelection();
}

// 过滤批量任务列表
function filterBatchTasks() {
    const searchTerm = document.getElementById('batchTaskSearchInput').value.toLowerCase().trim();
    filteredTasks = availableTasks.filter(task => 
        task.task_name.toLowerCase().includes(searchTerm) ||
        (task.task_id && task.task_id.toLowerCase().includes(searchTerm)) ||
        (task.top_categories && task.top_categories.some(cat => cat.toLowerCase().includes(searchTerm)))
    );
    renderTaskList('batchTaskListContainer');
    clearBatchTaskSelection();
}

// 清除单个迁移的任务选择
function clearTaskSelection() {
    document.getElementById('selectedTaskInfo').classList.add('d-none');
    document.getElementById('confirmMigrationBtn').disabled = true;
}

// 清除批量迁移的任务选择
function clearBatchTaskSelection() {
    document.getElementById('batchSelectedTaskInfo').classList.add('d-none');
    document.getElementById('previewBatchMigrationBtn').disabled = true;
    document.getElementById('confirmBatchMigrationBtn').disabled = true;
}

// 确认单个论文迁移
function confirmMigration() {
    const arxivId = document.getElementById('migrationPaperArxivId').value;
    const taskName = document.getElementById('selectedTaskName').textContent;
    const taskId = document.getElementById('selectedTaskIdForMigration').value;
    
    const confirmBtn = document.getElementById('confirmMigrationBtn');
    const originalText = confirmBtn.innerHTML;
    confirmBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> 迁移中...';
    confirmBtn.disabled = true;
    
    fetch('/api/migrate_paper_to_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            arxiv_id: arxivId,
            target_task_name: taskName,
            target_task_id: taskId || null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(`论文已成功迁移到任务: ${taskName}`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('migrationModal')).hide();
            setTimeout(() => location.reload(), 1500);
        } else {
            showAlert('迁移失败: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('迁移失败:', error);
        showAlert('网络错误，请稍后重试', 'error');
    })
    .finally(() => {
        confirmBtn.innerHTML = originalText;
        confirmBtn.disabled = false;
    });
}

// 确认批量迁移
function confirmBatchMigration() {
    const selectedPapers = getSelectedPapers();
    const taskName = document.getElementById('batchSelectedTaskName').textContent;
    const taskId = document.getElementById('batchSelectedTaskIdForMigration').value;
    
    const confirmBtn = document.getElementById('confirmBatchMigrationBtn');
    const originalText = confirmBtn.innerHTML;
    confirmBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> 迁移中...';
    confirmBtn.disabled = true;
    
    fetch('/api/batch_migrate_to_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            arxiv_ids: selectedPapers,
            target_task_name: taskName,
            target_task_id: taskId || null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            let message = `成功迁移 ${data.affected_rows} 篇论文到任务: ${taskName}`;
            if (data.warning) {
                message += `\n${data.warning}`;
            }
            showAlert(message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('batchMigrationModal')).hide();
            setTimeout(() => location.reload(), 2000);
        } else {
            showAlert('批量迁移失败: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('批量迁移失败:', error);
        showAlert('网络错误，请稍后重试', 'error');
    })
    .finally(() => {
        confirmBtn.innerHTML = originalText;
        confirmBtn.disabled = false;
    });
}

// 显示批量迁移预览
function showBatchMigrationPreview() {
    const selectedPapers = getSelectedPapers();
    const taskName = document.getElementById('batchSelectedTaskName').textContent;
    
    // 隐藏批量迁移模态框，显示预览模态框
    bootstrap.Modal.getInstance(document.getElementById('batchMigrationModal')).hide();
    const previewModal = new bootstrap.Modal(document.getElementById('batchMigrationPreviewModal'));
    previewModal.show();
    
    // 加载预览数据
    const previewContent = document.getElementById('migrationPreviewContent');
    previewContent.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">加载中...</span>
            </div>
            <p class="mt-2">正在生成迁移预览...</p>
        </div>
    `;
    
    fetch('/api/migration_preview', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            arxiv_ids: selectedPapers,
            target_task_name: taskName
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            renderMigrationPreview(data.data);
        } else {
            previewContent.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    生成预览失败: ${data.error}
                </div>
            `;
        }
    })
    .catch(error => {
        console.error('生成预览失败:', error);
        previewContent.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                网络错误，请稍后重试
            </div>
        `;
    });
}

// 渲染迁移预览
function renderMigrationPreview(previewData) {
    const { valid_papers, invalid_papers, summary } = previewData;
    const previewContent = document.getElementById('migrationPreviewContent');
    
    let html = `
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="bi bi-info-circle"></i> 迁移摘要</h6>
                    </div>
                    <div class="card-body">
                        <ul class="list-unstyled mb-0">
                            <li><strong>总选择:</strong> ${summary.total_selected} 篇</li>
                            <li><strong>有效论文:</strong> ${summary.valid_count} 篇</li>
                            <li><strong>无效论文:</strong> ${summary.invalid_count} 篇</li>
                            <li><strong>已在目标任务:</strong> ${summary.same_task_count} 篇</li>
                            <li><strong>需要迁移:</strong> ${summary.different_task_count} 篇</li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="bi bi-target"></i> 目标任务信息</h6>
                    </div>
                    <div class="card-body">
                        <ul class="list-unstyled mb-0">
                            <li><strong>当前论文数:</strong> ${summary.target_task_info.paper_count} 篇</li>
                            <li><strong>迁移后论文数:</strong> ${summary.target_task_info.paper_count + summary.different_task_count} 篇</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    if (summary.different_task_count > 0) {
        html += `
            <div class="mt-3">
                <h6><i class="bi bi-list"></i> 需要迁移的论文 (${summary.different_task_count} 篇)</h6>
                <div style="max-height: 300px; overflow-y: auto;">
                    <div class="list-group">
        `;
        
        valid_papers.filter(paper => paper.task_name !== document.getElementById('batchSelectedTaskName').textContent)
                    .forEach(paper => {
            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">${paper.title}</h6>
                            <p class="mb-1">
                                <small class="text-muted">
                                    当前任务: ${paper.task_name || '未分配'}
                                    ${paper.task_id ? ` (ID: ${paper.task_id})` : ''}
                                </small>
                            </p>
                        </div>
                        <small class="text-primary">${paper.arxiv_id}</small>
                    </div>
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
            </div>
        `;
    }
    
    if (summary.same_task_count > 0) {
        html += `
            <div class="mt-3">
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i>
                    有 ${summary.same_task_count} 篇论文已经在目标任务中，将不会被重复迁移。
                </div>
            </div>
        `;
    }
    
    if (summary.invalid_count > 0) {
        html += `
            <div class="mt-3">
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    有 ${summary.invalid_count} 篇论文不存在，将被跳过。
                </div>
            </div>
        `;
    }
    
    previewContent.innerHTML = html;
}

// 从预览执行批量迁移
function executeBatchMigrationFromPreview() {
    const selectedPapers = getSelectedPapers();
    const taskName = document.getElementById('batchSelectedTaskName').textContent;
    const taskId = document.getElementById('batchSelectedTaskIdForMigration').value;
    
    const executeBtn = document.getElementById('executeMigrationBtn');
    const originalText = executeBtn.innerHTML;
    executeBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> 执行中...';
    executeBtn.disabled = true;
    
    fetch('/api/batch_migrate_to_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            arxiv_ids: selectedPapers,
            target_task_name: taskName,
            target_task_id: taskId || null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            let message = `成功迁移 ${data.affected_rows} 篇论文到任务: ${taskName}`;
            if (data.warning) {
                message += `\n${data.warning}`;
            }
            showAlert(message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('batchMigrationPreviewModal')).hide();
            setTimeout(() => location.reload(), 2000);
        } else {
            showAlert('执行迁移失败: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('执行迁移失败:', error);
        showAlert('网络错误，请稍后重试', 'error');
    })
    .finally(() => {
        executeBtn.innerHTML = originalText;
        executeBtn.disabled = false;
    });
}

// ========== 增强的批量操作功能 ==========

// 全选当前页面的论文
function selectAllVisible() {
    const checkboxes = document.querySelectorAll('.paper-checkbox');
    checkboxes.forEach(checkbox => checkbox.checked = true);
    updateBatchToolbar();
}

// 导出给全局使用，添加相关度编辑功能和论文迁移功能
window.ExplorePaperData = {
    applyFilter,
    clearFilters,
    showAlert,
    copyToClipboard,
    exportData,
    refreshData,
    // 相关度编辑功能
    editRelevanceQuick,
    batchEditRelevance,
    // 论文迁移功能
    showMigrationModal,
    showBatchMigrationModal,
    selectAllVisible
};

// ========== Dify 知识库操作功能 ==========

/**
 * 上传论文到 Dify 知识库
 */
function uploadPaperToDify(arxivId) {
    console.log(`[Dify] 开始上传论文: ${arxivId}`);
    
    const uploadSection = document.getElementById('dify-upload-section');
    if (!uploadSection) {
        console.error('[Dify] 找不到dify-upload-section元素');
        showAlert('页面元素异常，请刷新页面重试', 'error');
        return;
    }
    
    const originalContent = uploadSection.innerHTML;
    
    // 显示上传状态
    uploadSection.innerHTML = `
        <button class="btn btn-info" disabled>
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">上传中...</span>
            </div>
            正在上传到知识库...
        </button>
    `;
    
    console.log(`[Dify] 发送上传请求到: /api/dify_upload/${arxivId}`);
    
    fetch(`/api/dify_upload/${arxivId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log(`[Dify] 上传响应状态: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Dify] 上传响应数据:', data);
        
        if (data.success) {
            showAlert('论文上传成功！', 'success');
            // 更新页面显示为已上传状态
            uploadSection.innerHTML = `
                <button class="btn btn-success" disabled>
                    <i class="bi bi-cloud-check"></i> 已上传到知识库
                </button>
                <button class="btn btn-outline-info btn-sm" onclick="verifyDifyDocument('${arxivId}')">
                    <i class="bi bi-shield-check"></i> 验证文档
                </button>
                <button class="btn btn-outline-danger btn-sm" onclick="removePaperFromDify('${arxivId}')">
                    <i class="bi bi-trash"></i> 从知识库移除
                </button>
            `;
            
            // 自动验证文档是否真正上传成功
            setTimeout(() => {
                console.log(`[Dify] 2秒后自动验证文档: ${arxivId}`);
                verifyDifyDocument(arxivId, true);
            }, 2000);
        } else {
            console.error('[Dify] 上传失败:', data.error);
            showAlert(`上传失败: ${data.error}`, 'error');
            // 恢复原始状态
            uploadSection.innerHTML = originalContent;
        }
    })
    .catch(error => {
        console.error('[Dify] 上传请求失败:', error);
        let errorMessage = '上传过程中发生网络错误';
        if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            errorMessage = '网络连接错误，请检查网络连接';
        } else if (error.message.includes('500')) {
            errorMessage = '服务器内部错误，请稍后重试';
        }
        showAlert(errorMessage, 'error');
        // 恢复原始状态
        uploadSection.innerHTML = originalContent;
    });
}

/**
 * 从 Dify 知识库移除论文
 */
function removePaperFromDify(arxivId) {
    console.log(`[Dify] 开始移除论文: ${arxivId}`);
    
    if (!confirm('确定要从知识库中移除这篇论文吗？此操作不可撤销。')) {
        console.log('[Dify] 用户取消了移除操作');
        return;
    }
    
    const uploadSection = document.getElementById('dify-upload-section');
    if (!uploadSection) {
        console.error('[Dify] 找不到dify-upload-section元素');
        showAlert('页面元素异常，请刷新页面重试', 'error');
        return;
    }
    
    const originalContent = uploadSection.innerHTML;
    
    // 显示移除状态
    uploadSection.innerHTML = `
        <button class="btn btn-warning" disabled>
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">移除中...</span>
            </div>
            正在从知识库移除...
        </button>
    `;
    
    console.log(`[Dify] 发送移除请求到: /api/dify_remove/${arxivId}`);
    
    fetch(`/api/dify_remove/${arxivId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log(`[Dify] 移除响应状态: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Dify] 移除响应数据:', data);
        
        if (data.success) {
            showAlert('论文已从知识库移除', 'success');
            // 更新页面显示
            uploadSection.innerHTML = `
                <button class="btn btn-outline-success" onclick="uploadPaperToDify('${arxivId}')">
                    <i class="bi bi-cloud-upload"></i> 上传到知识库
                </button>
            `;
        } else {
            console.error('[Dify] 移除失败:', data.error);
            showAlert(`移除失败: ${data.error}`, 'error');
            // 恢复原始状态
            uploadSection.innerHTML = originalContent;
        }
    })
    .catch(error => {
        console.error('[Dify] 移除请求失败:', error);
        let errorMessage = '移除过程中发生网络错误';
        if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            errorMessage = '网络连接错误，请检查网络连接';
        } else if (error.message.includes('500')) {
            errorMessage = '服务器内部错误，请稍后重试';
        }
        showAlert(errorMessage, 'error');
        // 恢复原始状态
        uploadSection.innerHTML = originalContent;
    });
}

/**
 * 验证论文是否存在于 Dify 服务器
 */
function verifyDifyDocument(arxivId, isAutoVerify = false) {
    console.log(`[Dify] 开始验证文档: ${arxivId}, 自动验证: ${isAutoVerify}`);
    
    if (!isAutoVerify) {
        // 显示验证说明对话框
        const confirmMessage = `确定要验证这篇论文在 Dify 服务器上的状态吗？\n\n验证将检查：\n• 文档是否真实存在于 Dify 服务器\n• 文档的索引状态和字符数\n• 本地记录与服务器状态的一致性`;
        if (!confirm(confirmMessage)) {
            console.log('[Dify] 用户取消了验证操作');
            return;
        }
    }
    
    const uploadSection = document.getElementById('dify-upload-section');
    if (!uploadSection) {
        console.error('[Dify] 找不到dify-upload-section元素');
        showAlert('页面元素异常，请刷新页面重试', 'error');
        return;
    }
    
    const originalContent = uploadSection.innerHTML;
    
    // 显示更清晰的验证状态
    uploadSection.innerHTML = `
        <div class="text-center p-3 border rounded bg-light">
            <div class="spinner-border text-primary mb-2" role="status">
                <span class="visually-hidden">验证中...</span>
            </div>
            <div class="fw-bold text-primary">正在验证文档状态...</div>
            <small class="text-muted">连接 Dify 服务器验证文档存在性</small>
        </div>
    `;
    
    console.log(`[Dify] 发送验证请求到: /api/dify_verify/${arxivId}`);
    
    fetch(`/api/dify_verify/${arxivId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log(`[Dify] 验证响应状态: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Dify] 验证响应数据:', data);
        
        if (data.success) {
            const result = data.data;
            console.log('[Dify] 验证结果:', result);
            
            if (result.verified) {
                // 验证成功 - 显示详细的成功信息
                const info = result.document_info;
                const successMessage = isAutoVerify ? 
                    '文档自动验证成功！' : 
                    `文档验证成功！\n\n验证详情：\n• 文档状态：${info?.status || '正常'}\n• 字符数：${info?.character_count || '未知'}\n• 索引状态：${info?.indexing_status || '未知'}`;
                
                showAlert(successMessage, 'success');
                
                uploadSection.innerHTML = `
                    <div class="d-grid gap-2">
                        <button class="btn btn-success" disabled>
                            <i class="bi bi-cloud-check"></i> 已上传到知识库
                            <span class="badge bg-light text-dark ms-1">✓ 已验证</span>
                        </button>
                        <div class="btn-group" role="group">
                            <button class="btn btn-outline-info btn-sm" onclick="verifyDifyDocument('${arxivId}')" title="重新验证文档状态">
                                <i class="bi bi-shield-check"></i> 重新验证
                            </button>
                            <button class="btn btn-outline-danger btn-sm" onclick="removePaperFromDify('${arxivId}')" title="从知识库移除">
                                <i class="bi bi-trash"></i> 移除
                            </button>
                        </div>
                    </div>
                `;
                
                // 如果不是自动验证，显示详细的验证结果
                if (!isAutoVerify && info) {
                    const detailsHtml = `
                        <div class="alert alert-success mt-2" role="alert">
                            <h6><i class="bi bi-check-circle"></i> 验证结果详情</h6>
                            <ul class="mb-0">
                                <li><strong>文档名称：</strong>${info.dify_name || '未知'}</li>
                                <li><strong>字符数：</strong>${info.character_count || 0}</li>
                                <li><strong>文档状态：</strong>${info.status || '未知'}</li>
                                <li><strong>索引状态：</strong>${info.indexing_status || '未知'}</li>
                            </ul>
                        </div>
                    `;
                    uploadSection.insertAdjacentHTML('afterend', detailsHtml);
                    
                    // 8秒后自动隐藏详情
                    setTimeout(() => {
                        const detailsAlert = uploadSection.nextElementSibling;
                        if (detailsAlert && detailsAlert.classList.contains('alert-success')) {
                            detailsAlert.remove();
                        }
                    }, 8000);
                }
                
            } else if (result.status === 'missing') {
                // 文档不存在 - 显示警告和解决方案
                console.warn('[Dify] 文档在Dify服务器上不存在');
                showAlert('⚠️ 验证失败：文档在 Dify 服务器上不存在！\n\n可能原因：\n• 文档已被手动删除\n• 知识库已被重置\n• 网络传输异常\n\n建议：重新上传或清理本地记录', 'warning');
                
                uploadSection.innerHTML = `
                    <div class="d-grid gap-2">
                        <div class="alert alert-warning mb-2" role="alert">
                            <i class="bi bi-exclamation-triangle"></i> 
                            <strong>状态异常：</strong>服务器上不存在此文档
                        </div>
                        <div class="btn-group" role="group">
                            <button class="btn btn-outline-primary btn-sm" onclick="uploadPaperToDify('${arxivId}')" title="重新上传到知识库">
                                <i class="bi bi-cloud-upload"></i> 重新上传
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" onclick="cleanMissingDifyRecord('${arxivId}')" title="清理本地错误记录">
                                <i class="bi bi-eraser"></i> 清理记录
                            </button>
                            <button class="btn btn-outline-info btn-sm" onclick="verifyDifyDocument('${arxivId}')" title="重新验证">
                                <i class="bi bi-arrow-repeat"></i> 重试验证
                            </button>
                        </div>
                    </div>
                `;
                
            } else if (result.status === 'not_uploaded') {
                // 未上传状态
                console.info('[Dify] 文档尚未上传到Dify');
                showAlert('ℹ️ 验证结果：文档尚未上传到 Dify 知识库', 'info');
                uploadSection.innerHTML = `
                    <button class="btn btn-outline-success" onclick="uploadPaperToDify('${arxivId}')">
                        <i class="bi bi-cloud-upload"></i> 上传到知识库
                    </button>
                `;
            } else {
                // 未知状态
                console.warn('[Dify] 未知的验证状态:', result.status);
                showAlert(`⚠️ 验证遇到未知状态: ${result.status}\n\n建议：稍后重试或联系管理员`, 'warning');
                uploadSection.innerHTML = originalContent;
            }
            
        } else {
            console.error('[Dify] 验证失败:', data.error);
            showAlert(`❌ 验证失败: ${data.error || '未知错误'}\n\n请检查网络连接或稍后重试`, 'error');
            // 恢复原始状态
            uploadSection.innerHTML = originalContent;
        }
    })
    .catch(error => {
        console.error('[Dify] 验证请求失败:', error);
        let errorMessage;
        if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            errorMessage = '❌ 网络连接错误\n\n请检查：\n• 网络连接状态\n• Dify 服务是否正常运行\n• 防火墙设置';
        } else if (error.message.includes('500')) {
            errorMessage = '❌ 服务器内部错误\n\n请稍后重试或联系管理员';
        } else {
            errorMessage = `❌ 验证过程中发生错误\n\n错误详情：${error.message}`;
        }
        showAlert(errorMessage, 'error');
        // 恢复原始状态
        uploadSection.innerHTML = originalContent;
    });
}

/**
 * 清理丢失的 Dify 文档记录
 */
function cleanMissingDifyRecord(arxivId) {
    console.log(`[Dify] 开始清理记录: ${arxivId}`);
    
    if (!confirm('确定要清理这篇论文的 Dify 记录吗？清理后论文状态将重置为未上传。')) {
        console.log('[Dify] 用户取消了清理操作');
        return;
    }
    
    const uploadSection = document.getElementById('dify-upload-section');
    if (!uploadSection) {
        console.error('[Dify] 找不到dify-upload-section元素');
        showAlert('页面元素异常，请刷新页面重试', 'error');
        return;
    }
    
    const originalContent = uploadSection.innerHTML;
    
    // 显示清理状态
    uploadSection.innerHTML = `
        <button class="btn btn-warning" disabled>
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">清理中...</span>
            </div>
            正在清理记录...
        </button>
    `;
    
    console.log(`[Dify] 发送清理请求到: /api/dify_clean/${arxivId}`);
    
    fetch(`/api/dify_clean/${arxivId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log(`[Dify] 清理响应状态: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Dify] 清理响应数据:', data);
        
        if (data.success) {
            showAlert('记录清理成功！论文状态已重置为未上传', 'success');
            uploadSection.innerHTML = `
                <button class="btn btn-outline-success" onclick="uploadPaperToDify('${arxivId}')">
                    <i class="bi bi-cloud-upload"></i> 上传到知识库
                </button>
            `;
        } else {
            console.error('[Dify] 清理失败:', data.error);
            showAlert(`清理失败: ${data.error}`, 'error');
            // 恢复原始状态
            uploadSection.innerHTML = originalContent;
        }
    })
    .catch(error => {
        console.error('[Dify] 清理请求失败:', error);
        let errorMessage = '清理过程中发生网络错误';
        if (error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            errorMessage = '网络连接错误，请检查网络连接';
        } else if (error.message.includes('500')) {
            errorMessage = '服务器内部错误，请稍后重试';
        }
        showAlert(errorMessage, 'error');
        // 恢复原始状态
        uploadSection.innerHTML = originalContent;
    });
}

// 将函数导出到全局作用域以便模板调用
window.editRelevanceQuick = editRelevanceQuick;
window.batchEditRelevance = batchEditRelevance;
window.showMigrationModal = showMigrationModal;
window.showBatchMigrationModal = showBatchMigrationModal;
window.selectAllVisible = selectAllVisible;
window.selectTask = selectTask;
window.filterTasks = filterTasks;
window.filterBatchTasks = filterBatchTasks;
window.confirmMigration = confirmMigration;
window.confirmBatchMigration = confirmBatchMigration;
window.showBatchMigrationPreview = showBatchMigrationPreview;
window.executeBatchMigrationFromPreview = executeBatchMigrationFromPreview;

// 导出 Dify 相关函数到全局作用域
window.uploadPaperToDify = uploadPaperToDify;
window.removePaperFromDify = removePaperFromDify;
window.verifyDifyDocument = verifyDifyDocument;
window.cleanMissingDifyRecord = cleanMissingDifyRecord;

// Note: startDeepAnalysis and cancelDeepAnalysis are defined in paper_detail.html template
// to avoid conflicts and ensure proper scope access

// ========== 深度分析配置功能 ==========

// 全局变量存储配置数据
let currentAnalysisConfig = {};
let availableModels = {};
let modelDetails = {};

/**
 * 初始化深度分析配置模态框
 */
function initAnalysisConfigModal() {
    console.log('[Config] 初始化深度分析配置模态框');
    
    // 绑定模态框显示事件
    const configModal = document.getElementById('analysisConfigModal');
    if (configModal) {
        configModal.addEventListener('show.bs.modal', function () {
            console.log('[Config] 模态框显示，开始加载配置');
            loadAnalysisConfig();
        });
    }
    
    // 绑定超时时间滑块事件
    const timeoutRange = document.getElementById('timeoutRange');
    const timeoutValue = document.getElementById('timeoutValue');
    if (timeoutRange && timeoutValue) {
        timeoutRange.addEventListener('input', function() {
            timeoutValue.textContent = this.value;
        });
    }
    
    // 绑定模型选择变化事件
    const analysisModelSelect = document.getElementById('analysisModelSelect');
    const visionModelSelect = document.getElementById('visionModelSelect');
    
    if (analysisModelSelect) {
        analysisModelSelect.addEventListener('change', function() {
            updateModelDetails();
        });
    }
    
    if (visionModelSelect) {
        visionModelSelect.addEventListener('change', function() {
            updateModelDetails();
        });
    }
    
    // 绑定按钮事件
    const saveConfigBtn = document.getElementById('saveConfigBtn');
    const resetConfigBtn = document.getElementById('resetConfigBtn');
    
    if (saveConfigBtn) {
        saveConfigBtn.addEventListener('click', saveAnalysisConfig);
    }
    
    if (resetConfigBtn) {
        resetConfigBtn.addEventListener('click', resetAnalysisConfig);
    }
}

/**
 * 加载深度分析配置
 */
function loadAnalysisConfig() {
    console.log('[Config] 开始加载深度分析配置');
    
    // 显示加载状态
    showConfigLoadingState();
    
    fetch('/api/analysis_config', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log(`[Config] 配置加载响应状态: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Config] 配置加载成功:', data);
        
        if (data.success) {
            // 存储数据
            currentAnalysisConfig = data.data.current_config;
            availableModels = data.data.available_models;
            modelDetails = data.data.model_details;
            
            // 填充配置表单
            populateConfigForm(data.data);
            
            // 显示配置表单
            showConfigForm();
        } else {
            throw new Error(data.error || '获取配置失败');
        }
    })
    .catch(error => {
        console.error('[Config] 配置加载失败:', error);
        showConfigErrorState(error.message);
    });
}

/**
 * 填充配置表单
 */
function populateConfigForm(configData) {
    console.log('[Config] 开始填充配置表单');
    
    const { current_config, available_models, model_details, recommended_models } = configData;
    
    // 填充分析模型下拉框
    const analysisModelSelect = document.getElementById('analysisModelSelect');
    if (analysisModelSelect) {
        analysisModelSelect.innerHTML = '<option value="">请选择分析模型...</option>';
        
        // 按提供商分组显示模型
        const modelsByProvider = {};
        available_models.analysis_models.forEach(modelKey => {
            const detail = model_details[modelKey];
            if (detail) {
                if (!modelsByProvider[detail.provider]) {
                    modelsByProvider[detail.provider] = [];
                }
                modelsByProvider[detail.provider].push({
                    key: modelKey,
                    detail: detail
                });
            }
        });
        
        // 添加分组选项
        Object.keys(modelsByProvider).sort().forEach(provider => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = `${provider.charAt(0).toUpperCase() + provider.slice(1)} 模型`;
            
            modelsByProvider[provider].forEach(model => {
                const option = document.createElement('option');
                option.value = model.key;
                option.textContent = `${model.detail.display_name} ${model.detail.is_local ? '🏠' : '☁️'}`;
                if (model.key === current_config.analysis_model) {
                    option.selected = true;
                }
                optgroup.appendChild(option);
            });
            
            analysisModelSelect.appendChild(optgroup);
        });
    }
    
    // 填充视觉模型下拉框
    const visionModelSelect = document.getElementById('visionModelSelect');
    if (visionModelSelect) {
        visionModelSelect.innerHTML = '<option value="">请选择视觉模型...</option>';
        
        available_models.vision_models.forEach(modelKey => {
            const detail = model_details[modelKey];
            if (detail) {
                const option = document.createElement('option');
                option.value = modelKey;
                option.textContent = `${detail.display_name} ${detail.is_local ? '🏠' : '☁️'}`;
                if (modelKey === current_config.vision_model) {
                    option.selected = true;
                }
                visionModelSelect.appendChild(option);
            }
        });
    }
    
    // 设置超时时间
    const timeoutRange = document.getElementById('timeoutRange');
    const timeoutValue = document.getElementById('timeoutValue');
    if (timeoutRange && timeoutValue) {
        timeoutRange.value = current_config.timeout;
        timeoutValue.textContent = current_config.timeout;
    }
    
    // 填充智能推荐
    populateModelRecommendations(recommended_models, model_details);
    
    // 更新模型详情
    updateModelDetails();
}

/**
 * 填充智能推荐
 */
function populateModelRecommendations(recommendations, modelDetails) {
    console.log('[Config] 填充智能推荐');
    
    // 推理模型推荐
    const reasoningModels = document.getElementById('reasoningModels');
    if (reasoningModels && recommendations.reasoning) {
        reasoningModels.innerHTML = '';
        recommendations.reasoning.forEach(modelKey => {
            if (modelDetails[modelKey]) {
                const detail = modelDetails[modelKey];
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'btn btn-outline-success btn-sm';
                button.innerHTML = `${detail.display_name} ${detail.is_local ? '🏠' : '☁️'}`;
                button.onclick = () => selectRecommendedModel('analysis', modelKey);
                reasoningModels.appendChild(button);
            }
        });
    }
    
    // 代码分析模型推荐
    const codingModels = document.getElementById('codingModels');
    if (codingModels && recommendations.coding) {
        codingModels.innerHTML = '';
        recommendations.coding.forEach(modelKey => {
            if (modelDetails[modelKey]) {
                const detail = modelDetails[modelKey];
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'btn btn-outline-info btn-sm';
                button.innerHTML = `${detail.display_name} ${detail.is_local ? '🏠' : '☁️'}`;
                button.onclick = () => selectRecommendedModel('analysis', modelKey);
                codingModels.appendChild(button);
            }
        });
    }
}

/**
 * 选择推荐模型
 */
function selectRecommendedModel(type, modelKey) {
    console.log(`[Config] 选择推荐模型: ${type} = ${modelKey}`);
    
    const selectElement = document.getElementById(type === 'analysis' ? 'analysisModelSelect' : 'visionModelSelect');
    if (selectElement) {
        selectElement.value = modelKey;
        updateModelDetails();
    }
}

/**
 * 更新模型详情显示
 */
function updateModelDetails() {
    console.log('[Config] 更新模型详情显示');
    
    const analysisModelKey = document.getElementById('analysisModelSelect').value;
    const visionModelKey = document.getElementById('visionModelSelect').value;
    
    // 更新分析模型详情
    const analysisModelDetails = document.getElementById('analysisModelDetails');
    if (analysisModelDetails && analysisModelKey && modelDetails[analysisModelKey]) {
        const detail = modelDetails[analysisModelKey];
        analysisModelDetails.innerHTML = `
            <ul class="list-unstyled mb-0">
                <li><strong>提供商:</strong> ${detail.provider}</li>
                <li><strong>类型:</strong> ${detail.is_local ? '本地模型 🏠' : '云端模型 ☁️'}</li>
                <li><strong>最大Token:</strong> ${detail.max_tokens || '未知'}</li>
                <li><strong>上下文长度:</strong> ${detail.context_length || '未知'}</li>
                <li><strong>支持函数:</strong> ${detail.supports_functions ? '✅' : '❌'}</li>
                <li><strong>支持视觉:</strong> ${detail.supports_vision ? '✅' : '❌'}</li>
            </ul>
            <div class="mt-2">
                <small class="text-muted">${detail.description}</small>
            </div>
        `;
    }
    
    // 更新视觉模型详情
    const visionModelDetails = document.getElementById('visionModelDetails');
    if (visionModelDetails && visionModelKey && modelDetails[visionModelKey]) {
        const detail = modelDetails[visionModelKey];
        visionModelDetails.innerHTML = `
            <ul class="list-unstyled mb-0">
                <li><strong>提供商:</strong> ${detail.provider}</li>
                <li><strong>类型:</strong> ${detail.is_local ? '本地模型 🏠' : '云端模型 ☁️'}</li>
                <li><strong>最大Token:</strong> ${detail.max_tokens || '未知'}</li>
                <li><strong>上下文长度:</strong> ${detail.context_length || '未知'}</li>
                <li><strong>支持函数:</strong> ${detail.supports_functions ? '✅' : '❌'}</li>
                <li><strong>支持视觉:</strong> ${detail.supports_vision ? '✅' : '❌'}</li>
            </ul>
            <div class="mt-2">
                <small class="text-muted">${detail.description}</small>
            </div>
        `;
    }
    
    // 显示模型详情区域
    const modelDetailsDiv = document.getElementById('modelDetails');
    const modelRecommendationsDiv = document.getElementById('modelRecommendations');
    if (analysisModelKey || visionModelKey) {
        if (modelDetailsDiv) modelDetailsDiv.style.display = 'block';
        if (modelRecommendationsDiv) modelRecommendationsDiv.style.display = 'block';
    }
}

/**
 * 保存深度分析配置
 */
function saveAnalysisConfig() {
    console.log('[Config] 开始保存深度分析配置');
    
    const analysisModel = document.getElementById('analysisModelSelect').value;
    const visionModel = document.getElementById('visionModelSelect').value;
    const timeout = parseInt(document.getElementById('timeoutRange').value);
    
    // 验证输入
    if (!analysisModel || !visionModel) {
        showConfigSaveStatus('error', '请选择分析模型和视觉模型');
        return;
    }
    
    const saveBtn = document.getElementById('saveConfigBtn');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="bi bi-arrow-repeat spinner-border spinner-border-sm"></i> 保存中...';
    saveBtn.disabled = true;
    
    const configData = {
        analysis_model: analysisModel,
        vision_model: visionModel,
        timeout: timeout
    };
    
    console.log('[Config] 提交配置数据:', configData);
    
    fetch('/api/analysis_config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(configData)
    })
    .then(response => {
        console.log(`[Config] 保存响应状态: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Config] 保存响应数据:', data);
        
        if (data.success) {
            showConfigSaveStatus('success', '配置保存成功！新配置将在下次分析时生效');
            currentAnalysisConfig = data.config;
            
            // 3秒后自动关闭模态框
            setTimeout(() => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('analysisConfigModal'));
                if (modal) modal.hide();
            }, 2000);
        } else {
            throw new Error(data.error || '保存失败');
        }
    })
    .catch(error => {
        console.error('[Config] 保存配置失败:', error);
        showConfigSaveStatus('error', `保存失败: ${error.message}`);
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

/**
 * 重置配置为默认值
 */
function resetAnalysisConfig() {
    console.log('[Config] 重置配置为默认值');
    
    if (!confirm('确定要重置为默认配置吗？')) {
        return;
    }
    
    // 重置表单值
    document.getElementById('analysisModelSelect').value = 'deepseek.DeepSeek_V3';
    document.getElementById('visionModelSelect').value = 'ollama.Qwen2_5_VL_7B';
    document.getElementById('timeoutRange').value = 600;
    document.getElementById('timeoutValue').textContent = '600';
    
    // 更新模型详情
    updateModelDetails();
    
    showConfigSaveStatus('info', '已重置为默认配置，点击保存按钮应用更改');
}

/**
 * 显示配置加载状态
 */
function showConfigLoadingState() {
    document.getElementById('configLoadingState').style.display = 'block';
    document.getElementById('analysisConfigForm').style.display = 'none';
    document.getElementById('configErrorState').style.display = 'none';
    document.getElementById('saveConfigBtn').style.display = 'none';
    document.getElementById('resetConfigBtn').style.display = 'none';
}

/**
 * 显示配置表单
 */
function showConfigForm() {
    document.getElementById('configLoadingState').style.display = 'none';
    document.getElementById('analysisConfigForm').style.display = 'block';
    document.getElementById('configErrorState').style.display = 'none';
    document.getElementById('saveConfigBtn').style.display = 'inline-block';
    document.getElementById('resetConfigBtn').style.display = 'inline-block';
}

/**
 * 显示配置错误状态
 */
function showConfigErrorState(errorMessage) {
    document.getElementById('configLoadingState').style.display = 'none';
    document.getElementById('analysisConfigForm').style.display = 'none';
    document.getElementById('configErrorState').style.display = 'block';
    document.getElementById('configErrorMessage').textContent = errorMessage;
    document.getElementById('saveConfigBtn').style.display = 'none';
    document.getElementById('resetConfigBtn').style.display = 'none';
}

/**
 * 显示配置保存状态
 */
function showConfigSaveStatus(type, message) {
    const statusDiv = document.getElementById('configSaveStatus');
    const messageSpan = document.getElementById('configSaveMessage');
    
    statusDiv.classList.remove('alert-info', 'alert-success', 'alert-warning', 'alert-danger');
    
    if (type === 'success') {
        statusDiv.classList.add('alert-success');
        messageSpan.innerHTML = `<i class="bi bi-check-circle"></i> ${message}`;
    } else if (type === 'error') {
        statusDiv.classList.add('alert-danger');
        messageSpan.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;
    } else if (type === 'warning') {
        statusDiv.classList.add('alert-warning');
        messageSpan.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;
    } else {
        statusDiv.classList.add('alert-info');
        messageSpan.innerHTML = `<i class="bi bi-info-circle"></i> ${message}`;
    }
    
    statusDiv.style.display = 'block';
    
    // 3秒后自动隐藏（除了成功消息）
    if (type !== 'success') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 5000);
    }
}

// 导出函数到全局作用域
window.loadAnalysisConfig = loadAnalysisConfig;
window.selectRecommendedModel = selectRecommendedModel;