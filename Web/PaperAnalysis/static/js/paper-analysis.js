// PaperAnalysis - 扩展功能脚本
// 包含论文收集、浏览和分析的高级功能

/**
 * 论文收集功能初始化
 */
function initCollectFunctionality() {
    // 任务配置表单处理
    const taskConfigForm = document.getElementById('taskConfigForm');
    if (taskConfigForm) {
        taskConfigForm.addEventListener('submit', handleTaskConfigSubmit);
    }
    
    // 任务状态监控
    initTaskStatusMonitoring();
    
    // 定时任务管理
    initScheduledTasksManagement();
}

/**
 * 论文浏览功能初始化  
 */
function initExploreFunctionality() {
    // 高级搜索功能
    initAdvancedSearch();
    
    // 批量操作功能
    initBatchOperations();
    
    // 论文详情交互
    initPaperDetailInteractions();
    
    // Dify集成功能
    initDifyIntegration();
}

/**
 * 深度分析功能初始化
 */
function initAnalysisFunctionality() {
    // 分析配置加载
    loadAnalysisConfig();
    
    // 分析任务监控
    initAnalysisTaskMonitoring();
    
    // 公式纠错功能
    initFormulaCorrectionFeatures();
}

/**
 * 任务配置表单提交处理
 */
async function handleTaskConfigSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const config = {
        task_name: formData.get('task_name'),
        search_query: formData.get('search_query'),
        llm_model_name: formData.get('llm_model_name'),
        search_mode: formData.get('search_mode'),
        max_papers_per_search: parseInt(formData.get('max_papers_per_search')),
        interval_seconds: parseInt(formData.get('interval_seconds')) || 3600
    };
    
    const mode = formData.get('execution_mode') || 'immediate';
    
    try {
        showAlert('正在启动任务...', 'info');
        
        const response = await fetch('/collect/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                mode: mode,
                config: config
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert(`任务启动成功！任务ID: ${result.task_id}`, 'success');
            
            // 重定向到任务状态页面
            setTimeout(() => {
                window.location.href = `/collect/status/${result.task_id}`;
            }, 1500);
        } else {
            showAlert(`任务启动失败: ${result.error}`, 'danger');
        }
    } catch (error) {
        showAlert(`网络错误: ${error.message}`, 'danger');
    }
}

/**
 * 任务状态监控
 */
function initTaskStatusMonitoring() {
    const statusContainer = document.getElementById('taskStatusContainer');
    if (!statusContainer) return;
    
    const taskId = statusContainer.dataset.taskId;
    if (!taskId) return;
    
    // 定期获取任务状态
    const statusInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/collect/task/${taskId}/status`);
            const result = await response.json();
            
            if (result.success) {
                updateTaskStatus(result.task_result);
                
                // 如果任务完成或失败，停止监控
                if (['completed', 'failed', 'stopped'].includes(result.task_result.status)) {
                    clearInterval(statusInterval);
                }
            }
        } catch (error) {
            console.error('获取任务状态失败:', error);
        }
    }, 5000);
}

/**
 * 更新任务状态显示
 */
function updateTaskStatus(taskResult) {
    const statusBadge = document.getElementById('taskStatusBadge');
    const progressBar = document.getElementById('taskProgressBar');
    const elapsedTime = document.getElementById('elapsedTime');
    const papersFound = document.getElementById('papersFound');
    
    if (statusBadge) {
        statusBadge.className = `badge bg-${getStatusBadgeClass(taskResult.status)}`;
        statusBadge.textContent = getStatusText(taskResult.status);
    }
    
    if (progressBar && taskResult.progress !== undefined) {
        progressBar.style.width = `${taskResult.progress}%`;
        progressBar.setAttribute('aria-valuenow', taskResult.progress);
    }
    
    if (elapsedTime && taskResult.elapsed_time) {
        elapsedTime.textContent = formatDuration(taskResult.elapsed_time);
    }
    
    if (papersFound && taskResult.papers_found !== undefined) {
        papersFound.textContent = taskResult.papers_found;
    }
}

/**
 * 高级搜索功能
 */
function initAdvancedSearch() {
    const advancedSearchToggle = document.getElementById('advancedSearchToggle');
    const advancedSearchPanel = document.getElementById('advancedSearchPanel');
    
    if (advancedSearchToggle && advancedSearchPanel) {
        advancedSearchToggle.addEventListener('click', function() {
            const isVisible = !advancedSearchPanel.classList.contains('d-none');
            
            if (isVisible) {
                advancedSearchPanel.classList.add('d-none');
                this.innerHTML = '<i class="bi bi-chevron-down me-1"></i>高级搜索';
            } else {
                advancedSearchPanel.classList.remove('d-none');
                this.innerHTML = '<i class="bi bi-chevron-up me-1"></i>收起高级搜索';
            }
        });
    }
    
    // 搜索建议功能
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        let suggestionTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(suggestionTimeout);
            suggestionTimeout = setTimeout(() => {
                showSearchSuggestions(this.value);
            }, 300);
        });
    }
}

/**
 * 批量操作功能
 */
function initBatchOperations() {
    const selectAllCheckbox = document.getElementById('selectAllPapers');
    const paperCheckboxes = document.querySelectorAll('.paper-checkbox');
    const batchOperationPanel = document.getElementById('batchOperationPanel');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            paperCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateBatchOperationPanel();
        });
    }
    
    paperCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateBatchOperationPanel);
    });
    
    function updateBatchOperationPanel() {
        const selectedCount = document.querySelectorAll('.paper-checkbox:checked').length;
        
        if (selectedCount > 0) {
            batchOperationPanel?.classList.remove('d-none');
            const countSpan = batchOperationPanel?.querySelector('.selected-count');
            if (countSpan) countSpan.textContent = selectedCount;
        } else {
            batchOperationPanel?.classList.add('d-none');
        }
    }
}

/**
 * 论文详情交互
 */
function initPaperDetailInteractions() {
    // 相关度评分功能
    const relevanceForm = document.getElementById('relevanceForm');
    if (relevanceForm) {
        relevanceForm.addEventListener('submit', handleRelevanceSubmit);
    }
    
    // 深度分析启动
    const analysisButtons = document.querySelectorAll('.start-analysis-btn');
    analysisButtons.forEach(button => {
        button.addEventListener('click', function() {
            const arxivId = this.dataset.arxivId;
            startDeepAnalysis(arxivId);
        });
    });
}

/**
 * Dify集成功能
 */
function initDifyIntegration() {
    const difyUploadButtons = document.querySelectorAll('.dify-upload-btn');
    difyUploadButtons.forEach(button => {
        button.addEventListener('click', function() {
            const arxivId = this.dataset.arxivId;
            uploadToDify(arxivId);
        });
    });
}

/**
 * 深度分析配置加载
 */
async function loadAnalysisConfig() {
    const configModal = document.getElementById('analysisConfigModal');
    if (!configModal) return;
    
    try {
        const response = await fetch('/api/analysis/config');
        const result = await response.json();
        
        if (result.success) {
            const config = result.data;
            populateAnalysisConfigForm(config);
        }
    } catch (error) {
        console.error('加载分析配置失败:', error);
    }
}

/**
 * 填充分析配置表单
 */
function populateAnalysisConfigForm(config) {
    const analysisModelSelect = document.getElementById('analysisModel');
    const visionModelSelect = document.getElementById('visionModel');
    const timeoutInput = document.getElementById('timeout');
    
    // 清空并填充分析模型选项
    if (analysisModelSelect) {
        analysisModelSelect.innerHTML = '<option value="">请选择分析模型</option>';
        config.available_models.analysis_models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            option.selected = model === config.current_config.analysis_model;
            analysisModelSelect.appendChild(option);
        });
    }
    
    // 清空并填充视觉模型选项
    if (visionModelSelect) {
        visionModelSelect.innerHTML = '<option value="">请选择视觉模型</option>';
        config.available_models.vision_models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            option.selected = model === config.current_config.vision_model;
            visionModelSelect.appendChild(option);
        });
    }
    
    // 设置超时时间
    if (timeoutInput) {
        timeoutInput.value = config.current_config.timeout;
    }
}

/**
 * 保存分析配置
 */
async function saveAnalysisConfig() {
    const form = document.getElementById('analysisConfigForm');
    const formData = new FormData(form);
    
    const config = {
        analysis_model: formData.get('analysis_model'),
        vision_model: formData.get('vision_model'),
        timeout: parseInt(formData.get('timeout'))
    };
    
    try {
        const response = await fetch('/api/analysis/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('配置保存成功！', 'success');
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('analysisConfigModal'));
            if (modal) modal.hide();
        } else {
            showAlert(`保存配置失败: ${result.error}`, 'danger');
        }
    } catch (error) {
        showAlert(`网络错误: ${error.message}`, 'danger');
    }
}

/**
 * 启动深度分析
 */
async function startDeepAnalysis(arxivId) {
    try {
        showAlert('正在启动深度分析...', 'info');
        
        const response = await fetch(`/api/analysis/paper/${arxivId}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: {
                    // 可以在这里添加特定的分析配置
                }
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('深度分析已启动，正在后台进行...', 'success');
            
            // 开始监控分析进度
            startAnalysisMonitoring(arxivId);
        } else {
            showAlert(`启动分析失败: ${result.error}`, 'danger');
        }
    } catch (error) {
        showAlert(`网络错误: ${error.message}`, 'danger');
    }
}

/**
 * 分析进度监控
 */
function startAnalysisMonitoring(arxivId) {
    const monitoringInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/analysis/paper/${arxivId}/status`);
            const result = await response.json();
            
            if (result.success) {
                const status = result.status;
                
                if (status === 'completed') {
                    clearInterval(monitoringInterval);
                    showAlert('深度分析完成！', 'success');
                    
                    // 可以选择重新加载页面或更新分析结果显示
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else if (status === 'failed') {
                    clearInterval(monitoringInterval);
                    showAlert('深度分析失败，请检查配置后重试', 'danger');
                }
            }
        } catch (error) {
            console.error('获取分析状态失败:', error);
        }
    }, 10000); // 每10秒检查一次
}

/**
 * 上传到Dify知识库
 */
async function uploadToDify(arxivId) {
    try {
        showAlert('正在上传到Dify知识库...', 'info');
        
        const response = await fetch(`/api/explore/dify_upload/${arxivId}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('成功上传到Dify知识库！', 'success');
        } else {
            showAlert(`上传失败: ${result.error}`, 'danger');
        }
    } catch (error) {
        showAlert(`网络错误: ${error.message}`, 'danger');
    }
}

/**
 * 工具函数 - 获取状态徽章类
 */
function getStatusBadgeClass(status) {
    const statusMap = {
        'pending': 'warning',
        'running': 'info', 
        'completed': 'success',
        'failed': 'danger',
        'stopped': 'secondary'
    };
    return statusMap[status] || 'secondary';
}

/**
 * 工具函数 - 获取状态文本
 */
function getStatusText(status) {
    const statusMap = {
        'pending': '等待中',
        'running': '运行中',
        'completed': '已完成',
        'failed': '失败',
        'stopped': '已停止'
    };
    return statusMap[status] || status;
}

/**
 * 工具函数 - 格式化持续时间
 */
function formatDuration(seconds) {
    if (!seconds) return '0秒';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    let result = [];
    if (hours > 0) result.push(`${hours}小时`);
    if (minutes > 0) result.push(`${minutes}分钟`);
    if (secs > 0) result.push(`${secs}秒`);
    
    return result.join(' ') || '0秒';
}

/**
 * 工具函数 - 显示警告消息
 */
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer') || 
                          document.querySelector('.container');
    
    if (!alertContainer) return;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // 插入到容器顶部
    alertContainer.insertBefore(alertDiv, alertContainer.firstChild);
    
    // 自动消失
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
}

// 暴露全局函数
window.saveAnalysisConfig = saveAnalysisConfig;
window.startDeepAnalysis = startDeepAnalysis;
window.uploadToDify = uploadToDify;