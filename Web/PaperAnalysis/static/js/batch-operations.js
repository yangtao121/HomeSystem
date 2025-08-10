/**
 * 批量操作相关的JavaScript功能
 * 处理论文的批量任务分配、迁移、Dify上传等操作
 */

// 全局变量
let currentBatchOperation = null;
let batchOperationData = {};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeBatchOperations();
});

/**
 * 初始化批量操作功能
 */
function initializeBatchOperations() {
    // 初始化模态框事件监听
    setupModalEventListeners();
    
    // 初始化表单验证
    setupFormValidation();
    
    // 初始化快捷键
    setupKeyboardShortcuts();
}

/**
 * 设置模态框事件监听
 */
function setupModalEventListeners() {
    // 任务分配模态框
    const assignModal = document.getElementById('assignTaskModal');
    if (assignModal) {
        assignModal.addEventListener('shown.bs.modal', function() {
            document.getElementById('assignTaskName').focus();
        });
    }
    
    // 迁移模态框
    const migrationModal = document.getElementById('migrationModal');
    if (migrationModal) {
        migrationModal.addEventListener('shown.bs.modal', function() {
            loadTaskList();
        });
    }
    
    // 批量迁移模态框
    const batchMigrationModal = document.getElementById('batchMigrationModal');
    if (batchMigrationModal) {
        batchMigrationModal.addEventListener('shown.bs.modal', function() {
            loadBatchTaskList();
        });
    }
}

/**
 * 设置表单验证
 */
function setupFormValidation() {
    // 任务名称输入验证
    const taskNameInput = document.getElementById('assignTaskName');
    if (taskNameInput) {
        taskNameInput.addEventListener('input', function() {
            const confirmBtn = document.getElementById('confirmAssignBtn');
            if (this.value.trim().length > 0) {
                confirmBtn.disabled = false;
            } else {
                confirmBtn.disabled = true;
            }
        });
    }
}

/**
 * 设置快捷键
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+A 全选
        if (e.ctrlKey && e.key === 'a' && !isInputFocused()) {
            e.preventDefault();
            selectAllVisible();
        }
        
        // Escape 清除选择
        if (e.key === 'Escape') {
            clearSelection();
        }
        
        // Ctrl+Shift+D 批量删除
        if (e.ctrlKey && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            batchDeletePapers();
        }
    });
}

/**
 * 检查是否有输入框获得焦点
 */
function isInputFocused() {
    const activeElement = document.activeElement;
    return activeElement && (
        activeElement.tagName === 'INPUT' || 
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.isContentEditable
    );
}

/**
 * 批量分配任务
 */
function batchAssignNewTasks() {
    const taskName = document.getElementById('newTaskName').value.trim();
    const taskId = document.getElementById('newTaskId').value.trim();
    
    if (!taskName) {
        showToast('请输入任务名称', 'warning');
        return;
    }
    
    if (selectedPapers.length === 0) {
        showToast('请先选择要分配任务的论文', 'warning');
        return;
    }
    
    // 显示确认对话框
    const confirmContent = `
        <p>将为 <strong>${selectedPapers.length}</strong> 篇论文分配以下任务：</p>
        <ul>
            <li><strong>任务名称:</strong> ${taskName}</li>
            ${taskId ? `<li><strong>任务ID:</strong> ${taskId}</li>` : ''}
        </ul>
        <p class="text-warning"><i class="bi bi-exclamation-triangle"></i> 此操作将覆盖这些论文的现有任务信息</p>
    `;
    
    showBatchConfirmModal('批量分配任务', confirmContent, function() {
        executeBatchAssignTask(taskName, taskId);
    });
}

/**
 * 执行批量任务分配
 */
function executeBatchAssignTask(taskName, taskId) {
    const arxivIds = selectedPapers.map(p => p.arxiv_id);
    
    showToast('正在批量分配任务...', 'info');
    
    fetch('/api/batch_assign_tasks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_ids: arxivIds,
            task_name: taskName,
            task_id: taskId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`成功为 ${data.updated_count} 篇论文分配任务`, 'success');
            // 清空输入框
            document.getElementById('newTaskName').value = '';
            document.getElementById('newTaskId').value = '';
            // 刷新页面或更新显示
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(`批量分配失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('批量分配任务失败:', error);
        showToast('批量分配任务时发生网络错误', 'danger');
    });
}

/**
 * 显示批量迁移模态框
 */
function showBatchMigrationModal() {
    if (selectedPapers.length === 0) {
        showToast('请先选择要迁移的论文', 'warning');
        return;
    }
    
    document.getElementById('batchMigrationPaperCount').textContent = selectedPapers.length;
    const modal = new bootstrap.Modal(document.getElementById('batchMigrationModal'));
    modal.show();
}

/**
 * 加载任务列表
 */
function loadTaskList() {
    const container = document.getElementById('taskListContainer');
    container.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p class="mt-2">正在加载任务列表...</p></div>';
    
    fetch('/api/get_tasks')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            renderTaskList(data.tasks, 'taskListContainer', 'selectTask');
        } else {
            container.innerHTML = '<div class="alert alert-danger">加载任务列表失败</div>';
        }
    })
    .catch(error => {
        console.error('加载任务列表失败:', error);
        container.innerHTML = '<div class="alert alert-danger">加载任务列表时发生网络错误</div>';
    });
}

/**
 * 加载批量任务列表
 */
function loadBatchTaskList() {
    const container = document.getElementById('batchTaskListContainer');
    container.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p class="mt-2">正在加载任务列表...</p></div>';
    
    fetch('/api/get_tasks')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            renderTaskList(data.tasks, 'batchTaskListContainer', 'selectBatchTask');
        } else {
            container.innerHTML = '<div class="alert alert-danger">加载任务列表失败</div>';
        }
    })
    .catch(error => {
        console.error('加载任务列表失败:', error);
        container.innerHTML = '<div class="alert alert-danger">加载任务列表时发生网络错误</div>';
    });
}

/**
 * 渲染任务列表
 */
function renderTaskList(tasks, containerId, selectFunctionName) {
    const container = document.getElementById(containerId);
    
    if (tasks.length === 0) {
        container.innerHTML = '<div class="alert alert-info">暂无任务数据</div>';
        return;
    }
    
    let html = '';
    tasks.forEach(task => {
        html += `
            <div class="task-item border rounded p-3 mb-2" style="cursor: pointer;" 
                 onclick="${selectFunctionName}('${task.task_name}', '${task.task_id || ''}', ${task.paper_count})">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${task.task_name}</h6>
                        ${task.task_id ? `<small class="text-muted">ID: ${task.task_id}</small><br>` : ''}
                        <small class="text-muted">包含 ${task.paper_count} 篇论文</small>
                    </div>
                    <div class="text-end">
                        <small class="text-muted">${formatDate(task.created_at)}</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

/**
 * 选择迁移任务
 */
function selectTask(taskName, taskId, paperCount) {
    // 高亮选中的任务
    document.querySelectorAll('.task-item').forEach(item => {
        item.classList.remove('border-primary', 'bg-light');
    });
    event.currentTarget.classList.add('border-primary', 'bg-light');
    
    // 显示选中的任务信息
    document.getElementById('selectedTaskName').textContent = taskName;
    document.getElementById('selectedTaskPaperCount').textContent = paperCount;
    document.getElementById('selectedTaskInfo').classList.remove('d-none');
    document.getElementById('selectedTaskIdForMigration').value = taskId;
    document.getElementById('confirmMigrationBtn').disabled = false;
}

/**
 * 选择批量迁移任务
 */
function selectBatchTask(taskName, taskId, paperCount) {
    // 高亮选中的任务
    document.querySelectorAll('#batchTaskListContainer .task-item').forEach(item => {
        item.classList.remove('border-success', 'bg-light');
    });
    event.currentTarget.classList.add('border-success', 'bg-light');
    
    // 显示选中的任务信息
    document.getElementById('batchSelectedTaskName').textContent = taskName;
    document.getElementById('batchSelectedTaskPaperCount').textContent = paperCount;
    document.getElementById('batchSelectedTaskInfo').classList.remove('d-none');
    document.getElementById('batchSelectedTaskIdForMigration').value = taskId;
    document.getElementById('previewBatchMigrationBtn').disabled = false;
    document.getElementById('confirmBatchMigrationBtn').disabled = false;
}

/**
 * 批量上传到Dify
 */
function batchUploadToDify() {
    // 立即显示确认对话框，确保函数被调用
    alert('批量上传函数被调用');
    
    console.log('batchUploadToDify called');
    console.log('selectedPapers:', selectedPapers);
    
    if (!selectedPapers || selectedPapers.length === 0) {
        console.log('No papers selected');
        showToast('请先选择要上传的论文', 'warning');
        return;
    }
    
    const arxivIds = selectedPapers.map(p => p.arxiv_id);
    console.log('arxivIds:', arxivIds);
    
    // 检查模态框是否存在
    const modalElement = document.getElementById('difyUploadProgressModal');
    if (!modalElement) {
        console.error('difyUploadProgressModal not found');
        showToast('上传进度模态框未找到', 'danger');
        return;
    }
    
    // 显示上传进度模态框
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
    
    // 初始化上传
    initializeDifyUpload(arxivIds);
}

/**
 * 初始化选中论文的批量上传到Dify
 */
function initializeDifyUpload(arxivIds) {
    // 重置进度信息
    document.getElementById('overallProgress').textContent = '0/' + arxivIds.length;
    document.getElementById('overallProgressBar').style.width = '0%';
    document.getElementById('overallProgressBar').textContent = '0%';
    document.getElementById('successCount').textContent = '0';
    document.getElementById('failedCount').textContent = '0';
    document.getElementById('totalCount').textContent = arxivIds.length;
    
    // 清空详细进度列表
    const progressList = document.getElementById('uploadDetailsList');
    if (progressList) {
        progressList.innerHTML = '';
    }
    
    // 隐藏错误汇总和完成操作按钮
    const errorSection = document.getElementById('errorSummarySection');
    if (errorSection) errorSection.style.display = 'none';
    
    const retryBtn = document.getElementById('retryFailedBtn');
    if (retryBtn) retryBtn.style.display = 'none';
    
    const exportBtn = document.getElementById('exportFailedBtn');
    if (exportBtn) exportBtn.style.display = 'none';
    
    const doneBtn = document.getElementById('uploadModalDoneBtn');
    if (doneBtn) doneBtn.style.display = 'none';
    
    const closeBtn = document.getElementById('uploadModalCloseBtn');
    if (closeBtn) closeBtn.disabled = true;
    
    // 开始批量上传
    startBatchDifyUpload(arxivIds);
}

/**
 * 开始选中论文的批量上传
 */
function startBatchDifyUpload(arxivIds) {
    // 调用后端API开始批量上传
    fetch('/api/dify_upload_all_eligible', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_ids: arxivIds,  // 只上传选中的论文
            exclude_already_uploaded: true,
            require_task_name: true
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            handleBatchUploadResult(data);
        } else {
            console.error('批量上传失败:', data);
            let errorMessage = data.error || '未知错误';
            showToast(`批量上传失败: ${errorMessage}`, 'danger');
            handleBatchUploadError(data.error);
        }
    })
    .catch(error => {
        console.error('批量上传网络错误:', error);
        let errorMessage = '网络连接失败';
        
        if (error.message.includes('HTTP 503')) {
            errorMessage = 'Dify 服务不可用，请检查服务状态';
        } else if (error.message.includes('HTTP 408')) {
            errorMessage = '上传操作超时，请稍后重试';
        } else if (error.message.includes('HTTP 500')) {
            errorMessage = '服务器内部错误，请查看日志';
        }
        
        showToast(`批量上传失败: ${errorMessage}`, 'danger');
        handleBatchUploadError(error.toString());
    });
}

/**
 * 处理批量上传结果
 */
function handleBatchUploadResult(result) {
    const {
        total_eligible,
        success_count,
        failed_count,
        successful_papers,
        failed_papers,
        failure_summary,
        suggestions,
        message
    } = result;
    
    // 更新进度显示
    document.getElementById('overallProgress').textContent = `${total_eligible}/${total_eligible}`;
    document.getElementById('overallProgressBar').style.width = '100%';
    document.getElementById('overallProgressBar').textContent = '100%';
    document.getElementById('successCount').textContent = success_count;
    document.getElementById('failedCount').textContent = failed_count;
    document.getElementById('totalCount').textContent = total_eligible;
    
    // 显示详细结果
    const progressList = document.getElementById('uploadDetailsList');
    if (progressList) {
        progressList.innerHTML = '';
        
        // 显示成功的论文
        if (successful_papers) {
            successful_papers.forEach(paper => {
                const item = document.createElement('div');
                item.className = 'mb-2 p-2 border rounded bg-success-subtle';
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${paper.arxiv_id}</strong>
                            <small class="text-muted d-block">${paper.title || '标题未知'}</small>
                        </div>
                        <span class="badge bg-success">
                            <i class="bi bi-check-circle"></i> 上传成功
                        </span>
                    </div>
                `;
                progressList.appendChild(item);
            });
        }
        
        // 显示失败的论文
        if (failed_papers) {
            failed_papers.forEach(paper => {
                const item = document.createElement('div');
                item.className = 'mb-2 p-2 border rounded bg-danger-subtle';
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${paper.arxiv_id}</strong>
                            <small class="text-muted d-block">${paper.title || '标题未知'}</small>
                            <small class="text-danger">${paper.error || '未知错误'}</small>
                        </div>
                        <span class="badge bg-danger">
                            <i class="bi bi-x-circle"></i> 上传失败
                        </span>
                    </div>
                `;
                progressList.appendChild(item);
            });
        }
    }
    
    // 显示错误汇总
    if (failed_count > 0) {
        showErrorSummary(failure_summary, suggestions);
    }
    
    // 启用关闭按钮和完成按钮
    const closeBtn = document.getElementById('uploadModalCloseBtn');
    if (closeBtn) closeBtn.disabled = false;
    
    const doneBtn = document.getElementById('uploadModalDoneBtn');
    if (doneBtn) doneBtn.style.display = 'inline-block';
    
    // 显示结果消息
    showToast(message || '批量上传完成', success_count > 0 ? 'success' : 'warning');
}

/**
 * 处理批量上传错误
 */
function handleBatchUploadError(error) {
    // 启用关闭按钮
    const closeBtn = document.getElementById('uploadModalCloseBtn');
    if (closeBtn) closeBtn.disabled = false;
    
    const doneBtn = document.getElementById('uploadModalDoneBtn');
    if (doneBtn) doneBtn.style.display = 'inline-block';
    
    // 更新进度条为错误状态
    const progressBar = document.getElementById('overallProgressBar');
    if (progressBar) {
        progressBar.classList.remove('progress-bar-animated');
        progressBar.classList.add('bg-danger');
        progressBar.textContent = '上传失败';
    }
}

/**
 * 显示错误汇总信息
 */
function showErrorSummary(failureSummary, suggestions) {
    const errorSection = document.getElementById('errorSummarySection');
    if (!errorSection) return;
    
    const categorySummary = document.getElementById('errorCategorySummary');
    const recommendationsSection = document.getElementById('recommendationsSection');
    
    // 生成错误分类汇总
    if (failureSummary && categorySummary) {
        let categoryHtml = '<div class="row">';
        Object.entries(failureSummary).forEach(([category, count]) => {
            categoryHtml += `
                <div class="col-md-4 mb-2">
                    <div class="card border-warning">
                        <div class="card-body text-center py-2">
                            <h6 class="card-title text-warning mb-1">${count}</h6>
                            <small class="text-muted">${category}</small>
                        </div>
                    </div>
                </div>
            `;
        });
        categoryHtml += '</div>';
        categorySummary.innerHTML = categoryHtml;
    }
    
    // 生成建议
    if (suggestions && suggestions.length > 0 && recommendationsSection) {
        let suggestionsHtml = '<h6>解决建议:</h6><ul>';
        suggestions.forEach(suggestion => {
            suggestionsHtml += `<li>${suggestion}</li>`;
        });
        suggestionsHtml += '</ul>';
        recommendationsSection.innerHTML = suggestionsHtml;
    }
    
    errorSection.style.display = 'block';
}

/**
 * 批量验证Dify文档
 */
function batchVerifyDifyDocuments() {
    // 显示验证进度模态框
    const modal = new bootstrap.Modal(document.getElementById('difyVerifyProgressModal'));
    modal.show();
    
    // 开始验证
    startBatchVerification();
}

/**
 * 开始批量验证Dify文档状态
 */
function startBatchVerification() {
    // 初始化验证进度显示
    document.getElementById('verifyOverallProgress').textContent = '0/0';
    document.getElementById('verifyOverallProgressBar').style.width = '0%';
    document.getElementById('verifyOverallProgressBar').textContent = '0%';
    document.getElementById('verifySuccessCount').textContent = '0';
    document.getElementById('verifyFailedCount').textContent = '0';
    document.getElementById('verifyMissingCount').textContent = '0';
    document.getElementById('verifyTotalCount').textContent = '0';
    
    // 更新状态消息
    document.getElementById('verifyStatusText').textContent = '正在初始化验证...';
    
    // 隐藏结果区域
    document.getElementById('verifyResultsSection').style.display = 'none';
    document.getElementById('verifyFailedSection').style.display = 'none';
    document.getElementById('verifyMissingSection').style.display = 'none';
    
    // 隐藏操作按钮
    document.getElementById('verifySuccessBtn').style.display = 'none';
    document.getElementById('batchReuploadBtn').style.display = 'none';
    document.getElementById('exportVerifyResultBtn').style.display = 'none';
    document.getElementById('verifyModalDoneBtn').style.display = 'none';
    
    // 调用后端API开始批量验证
    fetch('/api/dify_batch_verify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            handleBatchVerifyResult(data);
        } else {
            console.error('批量验证失败:', data);
            showToast(`批量验证失败: ${data.error}`, 'danger');
            handleBatchVerifyError(data.error);
        }
    })
    .catch(error => {
        console.error('批量验证网络错误:', error);
        showToast(`批量验证失败: 网络连接错误`, 'danger');
        handleBatchVerifyError(error.toString());
    });
}

/**
 * 处理批量验证结果
 */
function handleBatchVerifyResult(result) {
    const {
        total,
        verified,
        failed,
        missing,
        failed_papers,
        missing_papers,
        message
    } = result;
    
    // 更新进度显示
    document.getElementById('verifyOverallProgress').textContent = `${total}/${total}`;
    document.getElementById('verifyOverallProgressBar').style.width = '100%';
    document.getElementById('verifyOverallProgressBar').textContent = '100%';
    document.getElementById('verifySuccessCount').textContent = verified;
    document.getElementById('verifyFailedCount').textContent = failed;
    document.getElementById('verifyMissingCount').textContent = missing;
    document.getElementById('verifyTotalCount').textContent = total;
    
    // 更新状态消息
    let statusMessage = `验证完成！总计: ${total} 篇，验证通过: ${verified} 篇`;
    if (failed > 0) statusMessage += `，验证失败: ${failed} 篇`;
    if (missing > 0) statusMessage += `，文档丢失: ${missing} 篇`;
    
    document.getElementById('verifyStatusText').textContent = statusMessage;
    
    // 显示结果区域
    if (failed > 0 || missing > 0) {
        document.getElementById('verifyResultsSection').style.display = 'block';
        
        // 显示验证失败的文档
        if (failed > 0 && failed_papers) {
            const failedSection = document.getElementById('verifyFailedSection');
            const failedList = document.getElementById('verifyFailedList');
            
            let failedHtml = '';
            failed_papers.forEach(paper => {
                failedHtml += `
                    <div class="mb-2 p-2 border rounded bg-danger-subtle">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <strong>${paper.arxiv_id}</strong>
                                <small class="text-muted d-block">${paper.title || '标题未知'}</small>
                                <small class="text-danger">${paper.error || '验证失败'}</small>
                            </div>
                            <span class="badge bg-danger">
                                <i class="bi bi-x-circle"></i> 验证失败
                            </span>
                        </div>
                    </div>
                `;
            });
            
            failedList.innerHTML = failedHtml;
            failedSection.style.display = 'block';
        }
        
        // 显示文档丢失的论文
        if (missing > 0 && missing_papers) {
            const missingSection = document.getElementById('verifyMissingSection');
            const missingList = document.getElementById('verifyMissingList');
            
            let missingHtml = '';
            missing_papers.forEach(paper => {
                missingHtml += `
                    <div class="mb-2 p-2 border rounded bg-warning-subtle">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <strong>${paper.arxiv_id}</strong>
                                <small class="text-muted d-block">${paper.title || '标题未知'}</small>
                                <small class="text-warning">${paper.error || '文档在服务器上丢失'}</small>
                            </div>
                            <span class="badge bg-warning">
                                <i class="bi bi-exclamation-triangle"></i> 文档丢失
                            </span>
                        </div>
                    </div>
                `;
            });
            
            missingList.innerHTML = missingHtml;
            missingSection.style.display = 'block';
        }
    }
    
    // 显示操作按钮
    if (verified > 0 && failed === 0 && missing === 0) {
        document.getElementById('verifySuccessBtn').style.display = 'inline-block';
    }
    
    if (missing > 0) {
        document.getElementById('batchReuploadBtn').style.display = 'inline-block';
    }
    
    if (failed > 0 || missing > 0) {
        document.getElementById('exportVerifyResultBtn').style.display = 'inline-block';
    }
    
    document.getElementById('verifyModalDoneBtn').style.display = 'inline-block';
    
    // 显示结果消息
    showToast(message || '批量验证完成', verified > 0 ? 'success' : 'warning');
}

/**
 * 处理批量验证错误
 */
function handleBatchVerifyError(error) {
    // 更新状态消息
    document.getElementById('verifyStatusText').textContent = `验证失败: ${error}`;
    
    // 更新进度条为错误状态
    const progressBar = document.getElementById('verifyOverallProgressBar');
    if (progressBar) {
        progressBar.classList.remove('progress-bar-animated');
        progressBar.classList.add('bg-danger');
        progressBar.textContent = '验证失败';
    }
    
    // 显示完成按钮
    document.getElementById('verifyModalDoneBtn').style.display = 'inline-block';
}

/**
 * 批量删除论文
 */
function batchDeletePapers() {
    if (selectedPapers.length === 0) {
        showToast('请先选择要删除的论文', 'warning');
        return;
    }
    
    const confirmContent = `
        <div class="alert alert-danger">
            <i class="bi bi-exclamation-triangle"></i>
            <strong>警告：此操作不可恢复</strong>
        </div>
        <p>您即将删除 <strong>${selectedPapers.length}</strong> 篇论文：</p>
        <ul class="mb-3" style="max-height: 200px; overflow-y: auto;">
            ${selectedPapers.map(p => `<li>${p.title}</li>`).join('')}
        </ul>
        <p class="text-danger"><strong>这些论文将从数据库中永久删除，无法恢复。</strong></p>
    `;
    
    showBatchConfirmModal('确认批量删除', confirmContent, function() {
        executeBatchDelete();
    }, '确认删除', 'btn-danger');
}

/**
 * 执行批量删除
 */
function executeBatchDelete() {
    const arxivIds = selectedPapers.map(p => p.arxiv_id);
    
    showToast('正在批量删除论文...', 'info');
    
    fetch('/api/batch_delete_papers', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_ids: arxivIds
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`成功删除 ${data.deleted_count} 篇论文`, 'success');
            // 刷新页面
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(`批量删除失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('批量删除论文失败:', error);
        showToast('批量删除论文时发生网络错误', 'danger');
    });
}

/**
 * 显示批量确认模态框
 */
function showBatchConfirmModal(title, content, onConfirm, confirmText = '确认', confirmClass = 'btn-danger') {
    document.getElementById('batchConfirmModalLabel').innerHTML = `<i class="bi bi-exclamation-triangle text-warning"></i> ${title}`;
    document.getElementById('batchConfirmContent').innerHTML = content;
    
    const confirmBtn = document.getElementById('confirmBatchBtn');
    confirmBtn.textContent = confirmText;
    confirmBtn.className = `btn ${confirmClass}`;
    confirmBtn.onclick = function() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('batchConfirmModal'));
        modal.hide();
        onConfirm();
    };
    
    const modal = new bootstrap.Modal(document.getElementById('batchConfirmModal'));
    modal.show();
}

/**
 * 批量导出功能
 */
function batchExport() {
    if (selectedPapers.length === 0) {
        showToast('请先选择要导出的论文', 'warning');
        return;
    }
    
    const arxivIds = selectedPapers.map(p => p.arxiv_id);
    const params = new URLSearchParams();
    params.set('export', 'selected');
    params.set('arxiv_ids', arxivIds.join(','));
    
    window.location.href = `/api/export_papers?${params.toString()}`;
}

/**
 * 一键智能上传
 */
function oneClickUploadAll() {
    showToast('正在启动智能上传...', 'info');
    
    fetch('/api/one_click_upload', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 显示上传总结模态框
            showUploadSummary(data.data);
        } else {
            showToast(`智能上传失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('智能上传失败:', error);
        showToast('智能上传时发生网络错误', 'danger');
    });
}

/**
 * 显示上传总结
 */
function showUploadSummary(summaryData) {
    // 更新总结数据
    document.getElementById('summaryTotalCount').textContent = summaryData.total_count || 0;
    document.getElementById('summarySuccessCount').textContent = summaryData.success_count || 0;
    document.getElementById('summaryFailedCount').textContent = summaryData.failed_count || 0;
    document.getElementById('summarySkippedCount').textContent = summaryData.skipped_count || 0;
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('uploadSummaryModal'));
    modal.show();
}

/**
 * 格式化日期
 */
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN');
}

/**
 * 显示Toast通知
 */
function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    // 添加到页面
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.appendChild(toast);
    
    // 显示toast
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // 自动移除
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

/**
 * 批量从Dify知识库移除论文
 */
function batchRemoveFromDify() {
    if (!selectedPapers || selectedPapers.length === 0) {
        showToast('请先选择要从知识库移除的论文', 'warning');
        return;
    }
    
    const selectedCount = selectedPapers.length;
    if (!confirm(`确定要将选中的 ${selectedCount} 篇论文从Dify知识库中移除吗？\n\n此操作不可撤销！`)) {
        return;
    }
    
    showToast(`正在从Dify知识库移除 ${selectedCount} 篇论文...`, 'info');
    
    // 创建移除请求
    const arxivIds = selectedPapers.map(paper => paper.arxiv_id);
    
    fetch('/api/batch_remove_from_dify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            arxiv_ids: arxivIds
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`成功从Dify知识库移除 ${data.removed_count || selectedCount} 篇论文`, 'success');
            
            // 更新页面中的状态显示
            selectedPapers.forEach(paper => {
                const statusElement = document.getElementById(`dify-status-${paper.arxiv_id}`);
                if (statusElement) {
                    statusElement.innerHTML = `
                        <span class="badge bg-secondary">
                            <i class="bi bi-cloud-slash"></i> 未上传到Dify
                        </span>
                    `;
                }
                
                const buttonsElement = document.getElementById(`dify-buttons-${paper.arxiv_id}`);
                if (buttonsElement) {
                    buttonsElement.innerHTML = `
                        <button class="btn btn-sm btn-success w-100" 
                                onclick="uploadPaperToDifyList('${paper.arxiv_id}')"
                                title="上传到知识库">
                            <i class="bi bi-cloud-upload"></i>
                            <small class="d-block">上传</small>
                        </button>
                    `;
                }
            });
            
            // 清除选择状态
            clearSelection();
        } else {
            showToast(data.message || '从知识库移除论文时发生错误', 'error');
        }
    })
    .catch(error => {
        console.error('批量移除操作失败:', error);
        showToast('从知识库移除论文时发生网络错误', 'error');
    });
}

/**
 * 批量导出选中论文
 */
function batchExport() {
    if (!selectedPapers || selectedPapers.length === 0) {
        showToast('请先选择要导出的论文', 'warning');
        return;
    }
    
    const selectedCount = selectedPapers.length;
    showToast(`正在导出 ${selectedCount} 篇论文数据...`, 'info');
    
    // 创建导出请求
    const arxivIds = selectedPapers.map(paper => paper.arxiv_id);
    
    // 创建下载链接
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/api/export_papers';
    form.style.display = 'none';
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'arxiv_ids';
    input.value = JSON.stringify(arxivIds);
    form.appendChild(input);
    
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
    
    showToast(`论文数据导出请求已提交`, 'success');
}