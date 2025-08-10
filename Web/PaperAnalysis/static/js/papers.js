/**
 * 论文浏览页面的JavaScript功能
 * 处理搜索、分页、单个论文操作等基础功能
 */

// 全局变量
let currentPaper = null;
let editingRelevance = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializePapers();
});

/**
 * 初始化论文页面功能
 */
function initializePapers() {
    // 初始化工具提示
    initializeTooltips();
    
    // 设置搜索表单增强
    setupSearchEnhancements();
    
    // 初始化单个论文操作
    setupPaperActions();
    
    // 设置快捷键
    setupPaperKeyboardShortcuts();
    
    // 初始化分页
    setupPagination();
}

/**
 * 初始化工具提示
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * 设置搜索增强功能
 */
function setupSearchEnhancements() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        // 搜索建议功能
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                // 可以在这里添加搜索建议功能
            }, 300);
        });
        
        // Enter键搜索
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('searchForm').submit();
            }
        });
    }
    
    // 过滤器联动
    setupFilterInteractions();
}

/**
 * 设置过滤器交互
 */
function setupFilterInteractions() {
    const filters = ['categoryFilter', 'statusFilter', 'taskNameFilter', 'taskIdFilter'];
    
    filters.forEach(filterId => {
        const element = document.getElementById(filterId);
        if (element) {
            element.addEventListener('change', function() {
                // 自动提交表单（可选）
                // document.getElementById('searchForm').submit();
            });
        }
    });
}

/**
 * 设置单个论文操作
 */
function setupPaperActions() {
    // 设置Dify操作按钮事件
    document.addEventListener('click', function(e) {
        if (e.target.matches('[onclick*="uploadPaperToDifyList"]')) {
            e.preventDefault();
            const arxivId = extractArxivIdFromOnclick(e.target.getAttribute('onclick'));
            uploadSinglePaperToDify(arxivId);
        }
        
        if (e.target.matches('[onclick*="removePaperFromDifyList"]')) {
            e.preventDefault();
            const arxivId = extractArxivIdFromOnclick(e.target.getAttribute('onclick'));
            removeSinglePaperFromDify(arxivId);
        }
    });
}

/**
 * 从onclick属性中提取arxiv_id
 */
function extractArxivIdFromOnclick(onclickStr) {
    const match = onclickStr.match(/['"]([^'"]+)['"]/);
    return match ? match[1] : null;
}

/**
 * 设置快捷键
 */
function setupPaperKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // 不在输入框时的快捷键
        if (!isInputFocused()) {
            // S键 - 聚焦搜索框
            if (e.key === 's' || e.key === 'S') {
                e.preventDefault();
                const searchInput = document.getElementById('searchInput');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }
            
            // R键 - 清除过滤器
            if (e.key === 'r' || e.key === 'R') {
                e.preventDefault();
                window.location.href = window.location.pathname;
            }
        }
        
        // 全局快捷键
        // F5 - 刷新（浏览器默认）
        // Ctrl+F - 页面内搜索（浏览器默认）
    });
}

/**
 * 设置分页功能
 */
function setupPagination() {
    // 键盘导航
    document.addEventListener('keydown', function(e) {
        if (!isInputFocused()) {
            // 左箭头 - 上一页
            if (e.key === 'ArrowLeft') {
                const prevBtn = document.querySelector('.pagination .page-link[href*="page=' + (getCurrentPage() - 1) + '"]');
                if (prevBtn) {
                    e.preventDefault();
                    prevBtn.click();
                }
            }
            
            // 右箭头 - 下一页
            if (e.key === 'ArrowRight') {
                const nextBtn = document.querySelector('.pagination .page-link[href*="page=' + (getCurrentPage() + 1) + '"]');
                if (nextBtn) {
                    e.preventDefault();
                    nextBtn.click();
                }
            }
        }
    });
}

/**
 * 获取当前页码
 */
function getCurrentPage() {
    const activePageItem = document.querySelector('.pagination .page-item.active .page-link');
    return activePageItem ? parseInt(activePageItem.textContent) : 1;
}

/**
 * 显示任务分配模态框
 */
function showAssignTaskModal(arxivId, paperTitle) {
    currentPaper = { arxiv_id: arxivId, title: paperTitle };
    
    document.getElementById('assignPaperTitle').textContent = paperTitle;
    document.getElementById('assignTaskName').value = '';
    document.getElementById('assignTaskId').value = '';
    document.getElementById('confirmAssignBtn').disabled = true;
    
    const modal = new bootstrap.Modal(document.getElementById('assignTaskModal'));
    modal.show();
    
    // 聚焦到任务名称输入框
    setTimeout(() => {
        document.getElementById('assignTaskName').focus();
    }, 500);
}

/**
 * 确认分配任务
 */
function confirmAssignTask() {
    const taskName = document.getElementById('assignTaskName').value.trim();
    const taskId = document.getElementById('assignTaskId').value.trim();
    
    if (!taskName || !currentPaper) {
        showToast('请输入任务名称', 'warning');
        return;
    }
    
    showToast('正在分配任务...', 'info');
    
    fetch('/api/assign_task', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_id: currentPaper.arxiv_id,
            task_name: taskName,
            task_id: taskId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('任务分配成功', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('assignTaskModal'));
            modal.hide();
            
            // 更新页面显示
            updatePaperTaskDisplay(currentPaper.arxiv_id, taskName, taskId);
        } else {
            showToast(`任务分配失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('任务分配失败:', error);
        showToast('任务分配时发生网络错误', 'danger');
    });
}

/**
 * 更新论文任务显示
 */
function updatePaperTaskDisplay(arxivId, taskName, taskId) {
    // 查找并更新对应论文的任务信息显示
    const paperItem = document.querySelector(`[data-arxiv-id="${arxivId}"]`)?.closest('.paper-item');
    if (paperItem) {
        const taskInfoDiv = paperItem.querySelector('.paper-task-info');
        if (taskInfoDiv) {
            let html = `
                <span class="me-3">
                    <i class="bi bi-briefcase"></i>
                    <strong>任务:</strong> 
                    <span class="task-name-display" data-arxiv-id="${arxivId}">${taskName}</span>
                    <button class="btn btn-sm btn-outline-secondary ms-1 edit-task-btn" 
                            onclick="editTaskName('${arxivId}', '${taskName}')"
                            title="编辑任务名称">
                        <i class="bi bi-pencil"></i>
                    </button>
                </span>
            `;
            
            if (taskId) {
                html += `
                    <span class="me-3">
                        <i class="bi bi-hash"></i>
                        <strong>任务ID:</strong> <small class="text-muted">${taskId}</small>
                    </span>
                `;
            }
            
            taskInfoDiv.innerHTML = html;
            taskInfoDiv.classList.remove('alert', 'alert-warning', 'alert-sm', 'py-1');
            taskInfoDiv.classList.add('mt-2');
        }
        
        // 移除unassigned-paper类
        paperItem.classList.remove('unassigned-paper');
    }
}

/**
 * 编辑任务名称
 */
function editTaskName(arxivId, currentTaskName) {
    const newTaskName = prompt('请输入新的任务名称:', currentTaskName);
    if (newTaskName && newTaskName !== currentTaskName) {
        updateTaskName(arxivId, newTaskName);
    }
}

/**
 * 更新任务名称
 */
function updateTaskName(arxivId, newTaskName) {
    showToast('正在更新任务名称...', 'info');
    
    fetch('/api/update_task_name', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_id: arxivId,
            task_name: newTaskName
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('任务名称更新成功', 'success');
            // 更新页面显示
            const taskNameSpan = document.querySelector(`[data-arxiv-id="${arxivId}"].task-name-display`);
            if (taskNameSpan) {
                taskNameSpan.textContent = newTaskName;
            }
        } else {
            showToast(`任务名称更新失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('任务名称更新失败:', error);
        showToast('任务名称更新时发生网络错误', 'danger');
    });
}

/**
 * 快速编辑相关度
 */
function editRelevanceQuick(arxivId) {
    editingRelevance = arxivId;
    const score = prompt('请输入相关度评分 (1-5)，5为最相关:');
    if (score && !isNaN(score) && score >= 1 && score <= 5) {
        updateRelevanceScore(arxivId, parseInt(score));
    } else if (score !== null) {
        showToast('请输入有效的评分 (1-5)', 'warning');
    }
}

/**
 * 更新相关度评分
 */
function updateRelevanceScore(arxivId, score) {
    showToast('正在更新相关度评分...', 'info');
    
    fetch('/api/update_relevance_score', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_id: arxivId,
            score: score
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('相关度评分更新成功', 'success');
            // 可以刷新页面或者更新显示
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(`相关度评分更新失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('相关度评分更新失败:', error);
        showToast('相关度评分更新时发生网络错误', 'danger');
    });
}

/**
 * 上传单个论文到Dify
 */
function uploadSinglePaperToDify(arxivId) {
    showToast('正在上传到Dify知识库...', 'info');
    
    fetch(`/api/dify_upload/${arxivId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('上传到Dify知识库成功', 'success');
            // 更新按钮状态
            updateDifyButtonStatus(arxivId, true);
        } else {
            showToast(`上传失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('上传到Dify失败:', error);
        showToast('上传到Dify时发生网络错误', 'danger');
    });
}

/**
 * 从Dify移除单个论文
 */
function removeSinglePaperFromDify(arxivId) {
    if (!confirm('确定要从Dify知识库中移除此论文吗？')) {
        return;
    }
    
    showToast('正在从Dify知识库移除...', 'info');
    
    fetch(`/api/dify_remove/${arxivId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('从Dify知识库移除成功', 'success');
            // 更新按钮状态
            updateDifyButtonStatus(arxivId, false);
        } else {
            showToast(`移除失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('从Dify移除失败:', error);
        showToast('从Dify移除时发生网络错误', 'danger');
    });
}

/**
 * 更新Dify按钮状态
 */
function updateDifyButtonStatus(arxivId, isUploaded) {
    const statusDiv = document.getElementById(`dify-status-${arxivId}`);
    const buttonsDiv = document.getElementById(`dify-buttons-${arxivId}`);
    
    if (statusDiv) {
        if (isUploaded) {
            statusDiv.innerHTML = '<span class="badge bg-success"><i class="bi bi-cloud-check"></i> 已上传到Dify</span>';
        } else {
            statusDiv.innerHTML = '<span class="badge bg-secondary"><i class="bi bi-cloud-slash"></i> 未上传到Dify</span>';
        }
    }
    
    if (buttonsDiv) {
        if (isUploaded) {
            buttonsDiv.innerHTML = `
                <button class="btn btn-sm btn-outline-danger" 
                        onclick="removeSinglePaperFromDify('${arxivId}')"
                        title="从Dify知识库中移除此论文">
                    <i class="bi bi-cloud-minus"></i> 从知识库移除
                </button>
            `;
        } else {
            buttonsDiv.innerHTML = `
                <button class="btn btn-sm btn-outline-success" 
                        onclick="uploadSinglePaperToDify('${arxivId}')"
                        title="上传到知识库">
                    <i class="bi bi-cloud-upload"></i> 上传
                </button>
            `;
        }
    }
}

/**
 * 删除论文
 */
function deletePaper(arxivId, paperTitle) {
    if (!confirm(`确定要删除论文"${paperTitle}"吗？此操作无法撤销。`)) {
        return;
    }
    
    showToast('正在删除论文...', 'info');
    
    fetch('/api/delete_paper', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            arxiv_id: arxivId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('论文删除成功', 'success');
            // 移除论文项
            const paperItem = document.querySelector(`[data-arxiv-id="${arxivId}"]`)?.closest('.paper-item');
            if (paperItem) {
                paperItem.remove();
            }
        } else {
            showToast(`论文删除失败: ${data.error}`, 'danger');
        }
    })
    .catch(error => {
        console.error('论文删除失败:', error);
        showToast('论文删除时发生网络错误', 'danger');
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