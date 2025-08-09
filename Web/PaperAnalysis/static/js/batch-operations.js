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
    if (selectedPapers.length === 0) {
        showToast('请先选择要上传的论文', 'warning');
        return;
    }
    
    const arxivIds = selectedPapers.map(p => p.arxiv_id);
    
    // 显示上传进度模态框
    const modal = new bootstrap.Modal(document.getElementById('difyUploadProgressModal'));
    modal.show();
    
    // 初始化上传
    initializeDifyUpload(arxivIds);
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