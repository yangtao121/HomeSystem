// PaperGather 配置页面 JavaScript
// 处理历史任务和配置预设功能

// 工具函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showNotification(message, type) {
    // 创建 Bootstrap 警告提示
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'danger' ? 'alert-danger' : 
                      type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const alert = $(`
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    // 添加到页面顶部容器
    let container = $('#alertContainer');
    if (container.length === 0) {
        container = $('<div id="alertContainer" class="container mt-3"></div>');
        $('main').prepend(container);
    }
    
    container.append(alert);
    
    // 3秒后自动消失
    setTimeout(() => {
        alert.alert('close');
    }, 3000);
}

function formatDuration(seconds) {
    if (!seconds) return '0秒';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    let result = [];
    if (hours > 0) result.push(`${hours}小时`);
    if (minutes > 0) result.push(`${minutes}分钟`);
    if (secs > 0) result.push(`${secs}秒`);
    
    return result.length > 0 ? result.join('') : '0秒';
}

// API 工具函数
const API = {
    async request(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },
    
    async get(url) {
        return this.request(url, { method: 'GET' });
    },
    
    async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
};

$(document).ready(function() {
    // 历史任务相关功能
    const HistoryTaskManager = {
        currentTasks: [],
        
        // 显示历史任务模态框
        showModal: function() {
            $('#historyTaskModal').modal('show');
            this.loadHistoryTasks();
        },
        
        // 加载历史任务
        loadHistoryTasks: function() {
            const statusFilter = $('#historyStatusFilter').val();
            const searchTerm = $('#historySearchInput').val().trim();
            
            $('#historyTaskList').html(`
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                </div>
            `);
            
            // API请求参数
            let params = new URLSearchParams({
                page: 1,
                per_page: 50
            });
            
            if (statusFilter) {
                params.append('status', statusFilter);
            }
            
            API.get(`/api/task/history?${params.toString()}`)
                .then(response => {
                    if (response.success) {
                        this.currentTasks = response.data.tasks;
                        this.renderHistoryTasks(response.data.tasks, searchTerm);
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('加载历史任务失败:', error);
                    $('#historyTaskList').html(`
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            加载历史任务失败: ${error.message}
                        </div>
                    `);
                });
        },
        
        // 渲染历史任务列表
        renderHistoryTasks: function(tasks, searchTerm = '') {
            if (!tasks || tasks.length === 0) {
                $('#historyTaskList').html(`
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-inbox fa-3x mb-3"></i>
                        <p>暂无历史任务</p>
                    </div>
                `);
                return;
            }
            
            // 搜索过滤
            let filteredTasks = tasks;
            if (searchTerm) {
                filteredTasks = tasks.filter(task => {
                    const config = task.config || {};
                    return (config.search_query || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                           (config.user_requirements || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                           (task.task_id || '').toLowerCase().includes(searchTerm.toLowerCase());
                });
            }
            
            if (filteredTasks.length === 0) {
                $('#historyTaskList').html(`
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-search fa-3x mb-3"></i>
                        <p>未找到匹配的任务</p>
                    </div>
                `);
                return;
            }
            
            let html = '<div class="list-group">';
            
            filteredTasks.forEach(task => {
                const config = task.config || {};
                const startTime = new Date(task.start_time).toLocaleString('zh-CN');
                const statusBadge = this.getStatusBadge(task.status);
                const duration = task.duration ? formatDuration(task.duration) : '未知';
                
                html += `
                    <div class="list-group-item list-group-item-action">
                        <div class="d-flex w-100 justify-content-between">
                            <div class="flex-grow-1">
                                <div class="row">
                                    <div class="col-md-8">
                                        <h6 class="mb-1">
                                            <i class="fas fa-search me-1"></i>
                                            ${this.escapeHtml(config.search_query || '未知查询')}
                                        </h6>
                                        <p class="mb-1 text-muted small">
                                            ${this.escapeHtml(config.user_requirements || '无描述').substring(0, 100)}...
                                        </p>
                                        <small class="text-muted">
                                            <i class="fas fa-clock me-1"></i>${startTime}
                                            <span class="ms-2"><i class="fas fa-stopwatch me-1"></i>${duration}</span>
                                            <span class="ms-2"><i class="fas fa-search me-1"></i>最大论文数: ${config.max_papers_per_search || 20}</span>
                                        </small>
                                    </div>
                                    <div class="col-md-4 text-end">
                                        <div class="mb-2">
                                            ${statusBadge}
                                        </div>
                                        <div class="btn-group btn-group-sm">
                                            <button class="btn btn-outline-primary" onclick="HistoryTaskManager.loadTaskConfig('${task.task_id}')">
                                                <i class="fas fa-download me-1"></i>加载配置
                                            </button>
                                            <button class="btn btn-outline-info" onclick="HistoryTaskManager.viewTaskDetails('${task.task_id}')">
                                                <i class="fas fa-eye me-1"></i>查看详情
                                            </button>
                                            <button class="btn btn-outline-warning" onclick="HistoryTaskManager.editTask('${task.task_id}')">
                                                <i class="fas fa-edit me-1"></i>编辑
                                            </button>
                                            <button class="btn btn-outline-danger" onclick="HistoryTaskManager.deleteTask('${task.task_id}', '${this.escapeHtml(config.search_query || '未知查询').substring(0, 30)}')">
                                                <i class="fas fa-trash me-1"></i>删除
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            $('#historyTaskList').html(html);
        },
        
        // 获取状态徽章
        getStatusBadge: function(status) {
            const statusMap = {
                'completed': { class: 'success', text: '已完成', icon: 'check-circle' },
                'failed': { class: 'danger', text: '失败', icon: 'times-circle' },
                'stopped': { class: 'secondary', text: '已停止', icon: 'stop-circle' },
                'running': { class: 'info', text: '运行中', icon: 'play-circle' },
                'pending': { class: 'warning', text: '等待中', icon: 'clock' }
            };
            
            const statusInfo = statusMap[status] || { class: 'secondary', text: status, icon: 'question-circle' };
            return `<span class="badge bg-${statusInfo.class}">
                        <i class="fas fa-${statusInfo.icon} me-1"></i>${statusInfo.text}
                    </span>`;
        },
        
        // 转义HTML
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        // 加载任务配置
        loadTaskConfig: function(taskId) {
            API.get(`/api/task/config/${taskId}`)
                .then(response => {
                    if (response.success) {
                        // 修复数据访问路径：API返回的数据结构为 {data: {task_id, config}}
                        this.fillConfigForm(response.data.config);
                        
                        // 修复可访问性问题：在隐藏模态框前清除焦点
                        if (document.activeElement) {
                            document.activeElement.blur();
                        }
                        
                        // 隐藏模态框，并在完成后设置合适的焦点
                        const modal = $('#historyTaskModal');
                        modal.one('hidden.bs.modal', function() {
                            // 将焦点设置到第一个表单输入字段，提供更好的用户体验
                            $('#search_query').focus();
                        });
                        modal.modal('hide');
                        
                        showNotification('配置已加载成功', 'success');
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('加载任务配置失败:', error);
                    showNotification(`加载配置失败: ${error.message}`, 'danger');
                });
        },
        
        // 填充配置表单
        fillConfigForm: function(config) {
            // 基本配置
            if (config.search_query) $('#search_query').val(config.search_query);
            if (config.user_requirements) $('#user_requirements').val(config.user_requirements);
            if (config.llm_model_name) $('#llm_model_name').val(config.llm_model_name);
            
            // 任务信息配置
            if (config.task_name) $('#task_name').val(config.task_name);
            
            // 高级模型配置
            if (config.abstract_analysis_model) $('#abstract_analysis_model').val(config.abstract_analysis_model);
            if (config.full_paper_analysis_model) $('#full_paper_analysis_model').val(config.full_paper_analysis_model);
            if (config.deep_analysis_model) $('#deep_analysis_model').val(config.deep_analysis_model);
            if (config.vision_model) $('#vision_model').val(config.vision_model);
            if (config.video_analysis_model) $('#video_analysis_model').val(config.video_analysis_model);
            
            // 高级配置
            if (config.max_papers_per_search !== undefined) $('#max_papers_per_search').val(config.max_papers_per_search);
            if (config.relevance_threshold !== undefined) {
                $('#relevance_threshold').val(config.relevance_threshold);
                $('#relevance_threshold_value').text((config.relevance_threshold * 100).toFixed(0) + '%');
            }
            if (config.deep_analysis_threshold !== undefined) {
                $('#deep_analysis_threshold').val(config.deep_analysis_threshold);
                $('#deep_analysis_threshold_value').text((config.deep_analysis_threshold * 100).toFixed(0) + '%');
            }
            
            // 深度分析配置
            if (config.enable_deep_analysis !== undefined) {
                $('#enable_deep_analysis').prop('checked', config.enable_deep_analysis);
            }
            if (config.ocr_char_limit_for_analysis !== undefined) {
                $('#ocr_char_limit_for_analysis').val(config.ocr_char_limit_for_analysis);
            }
            
            // 搜索模式
            if (config.search_mode) $('#search_mode').val(config.search_mode);
            
            // 搜索模式相关的年份配置
            if (config.start_year !== undefined) $('#start_year').val(config.start_year);
            if (config.end_year !== undefined) $('#end_year').val(config.end_year);
            if (config.after_year !== undefined) $('#after_year').val(config.after_year);
            
            // 定时任务配置
            if (config.interval_seconds && config.interval_seconds > 0) {
                $('#interval_seconds').val(config.interval_seconds);
                // 切换到定时模式
                $('input[name="execution_mode"][value="scheduled"]').prop('checked', true);
                $('.execution-mode-card').removeClass('selected');
                $('.execution-mode-card[data-mode="scheduled"]').addClass('selected');
                $('#scheduled_config').show();
            }
            
            // 补充深度分析配置
            if (config.enable_deep_analysis !== undefined) {
                $('#enable_deep_analysis').prop('checked', config.enable_deep_analysis);
            }
            if (config.ocr_char_limit_for_analysis !== undefined) {
                $('#ocr_char_limit_for_analysis').val(config.ocr_char_limit_for_analysis);
            }
            // 补充视频分析配置
            if (config.enable_video_analysis !== undefined) {
                $('#enable_video_analysis').prop('checked', config.enable_video_analysis);
            }
            
            // 触发change事件以更新界面
            $('#search_mode').trigger('change');
        },
        
        // 查看任务详情
        viewTaskDetails: function(taskId) {
            // 在新窗口中打开任务详情页面
            window.open(`/task/result/${taskId}`, '_blank');
        },
        
        // 编辑历史任务
        editTask: function(taskId) {
            // 先获取任务配置
            API.get(`/api/task/config/${taskId}`)
                .then(response => {
                    if (response.success) {
                        // 存储当前编辑的任务ID
                        this.currentEditingTaskId = taskId;
                        
                        // 填充编辑表单
                        this.fillEditForm(response.data);
                        
                        // 显示编辑模态框
                        $('#editTaskModal').modal('show');
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('获取任务配置失败:', error);
                    showNotification(`获取任务配置失败: ${error.message}`, 'danger');
                });
        },
        
        // 填充编辑表单
        fillEditForm: function(config) {
            // 基本配置
            $('#edit_task_name').val(config.task_name || '');
            $('#edit_search_query').val(config.search_query || '');
            $('#edit_user_requirements').val(config.user_requirements || '');
            $('#edit_llm_model_name').val(config.llm_model_name || '');
            
            // 高级模型配置
            $('#edit_abstract_analysis_model').val(config.abstract_analysis_model || '');
            $('#edit_full_paper_analysis_model').val(config.full_paper_analysis_model || '');
            $('#edit_deep_analysis_model').val(config.deep_analysis_model || '');
            $('#edit_vision_model').val(config.vision_model || '');
            
            // 高级配置
            $('#edit_max_papers_per_search').val(config.max_papers_per_search || 20);
            $('#edit_relevance_threshold').val(config.relevance_threshold || 0.7);
            $('#edit_deep_analysis_threshold').val(config.deep_analysis_threshold || 0.8);
            $('#edit_search_mode').val(config.search_mode || 'latest');
            $('#edit_ocr_char_limit_for_analysis').val(config.ocr_char_limit_for_analysis || 10000);
            
            // 更新阈值显示
            $('#edit_relevance_threshold_value').text(((config.relevance_threshold || 0.7) * 100).toFixed(0) + '%');
            $('#edit_deep_analysis_threshold_value').text(((config.deep_analysis_threshold || 0.8) * 100).toFixed(0) + '%');
            
            // 布尔值配置
            $('#edit_enable_deep_analysis').prop('checked', config.enable_deep_analysis !== false);
            
            // 搜索模式相关配置
            this.updateEditSearchModeFields(config.search_mode || 'latest');
            if (config.start_year) $('#edit_start_year').val(config.start_year);
            if (config.end_year) $('#edit_end_year').val(config.end_year);
            if (config.after_year) $('#edit_after_year').val(config.after_year);
        },
        
        // 更新编辑表单中的搜索模式字段
        updateEditSearchModeFields: function(mode) {
            $('#edit_date_range_config, #edit_after_year_config').hide();
            
            if (mode === 'date_range') {
                $('#edit_date_range_config').show();
            } else if (mode === 'after_year') {
                $('#edit_after_year_config').show();
            }
        },
        
        // 保存编辑的任务
        saveEditedTask: function() {
            if (!this.currentEditingTaskId) {
                showNotification('未找到要编辑的任务ID', 'danger');
                return;
            }
            
            // 收集表单数据
            const updatedConfig = {
                task_name: $('#edit_task_name').val(),
                search_query: $('#edit_search_query').val(),
                user_requirements: $('#edit_user_requirements').val(),
                llm_model_name: $('#edit_llm_model_name').val(),
                abstract_analysis_model: $('#edit_abstract_analysis_model').val() || '',
                full_paper_analysis_model: $('#edit_full_paper_analysis_model').val() || '',
                deep_analysis_model: $('#edit_deep_analysis_model').val() || '',
                vision_model: $('#edit_vision_model').val() || '',
                max_papers_per_search: parseInt($('#edit_max_papers_per_search').val()) || 20,
                relevance_threshold: parseFloat($('#edit_relevance_threshold').val()) || 0.7,
                deep_analysis_threshold: parseFloat($('#edit_deep_analysis_threshold').val()) || 0.8,
                search_mode: $('#edit_search_mode').val() || 'latest',
                ocr_char_limit_for_analysis: parseInt($('#edit_ocr_char_limit_for_analysis').val()) || 10000,
                enable_deep_analysis: $('#edit_enable_deep_analysis').is(':checked')
            };
            
            // 添加搜索模式相关配置
            const searchMode = $('#edit_search_mode').val();
            if (searchMode === 'date_range') {
                updatedConfig.start_year = parseInt($('#edit_start_year').val()) || null;
                updatedConfig.end_year = parseInt($('#edit_end_year').val()) || null;
            } else if (searchMode === 'after_year') {
                updatedConfig.after_year = parseInt($('#edit_after_year').val()) || null;
            }
            
            const updateData = {
                config: updatedConfig
            };
            
            // 显示保存中状态
            const saveBtn = $('#saveEditedTaskBtn');
            const originalText = saveBtn.html();
            saveBtn.html('<i class="fas fa-spinner fa-spin me-1"></i>保存中...').prop('disabled', true);
            
            // 发送更新请求
            API.request(`/api/task/history/${this.currentEditingTaskId}`, {
                method: 'PUT',
                body: JSON.stringify(updateData),
                headers: {
                    'Content-Type': 'application/json'
                }
            })
                .then(response => {
                    if (response.success) {
                        // 修复可访问性问题：在隐藏模态框前清除焦点
                        if (document.activeElement) {
                            document.activeElement.blur();
                        }
                        
                        $('#editTaskModal').modal('hide');
                        showNotification('历史任务更新成功', 'success');
                        // 重新加载任务列表
                        this.loadHistoryTasks();
                    } else {
                        throw new Error(response.error || '更新失败');
                    }
                })
                .catch(error => {
                    console.error('更新历史任务失败:', error);
                    showNotification(`更新失败: ${error.message}`, 'danger');
                })
                .finally(() => {
                    // 恢复按钮状态
                    saveBtn.html(originalText).prop('disabled', false);
                });
        },
        
        // 删除历史任务
        deleteTask: function(taskId, taskName) {
            const confirmMessage = `确定要删除历史任务"${taskName}"吗？\n\n注意：此操作不可撤销，任务记录将被永久删除。`;
            
            if (!confirm(confirmMessage)) {
                return;
            }
            
            // 显示删除中状态
            const deleteBtn = document.querySelector(`button[onclick*="deleteTask('${taskId}'"]`);
            const originalText = deleteBtn.innerHTML;
            deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>删除中...';
            deleteBtn.disabled = true;
            
            API.delete(`/api/task/history/${taskId}`)
                .then(response => {
                    if (response.success) {
                        showNotification('历史任务删除成功', 'success');
                        // 重新加载任务列表
                        this.loadHistoryTasks();
                    } else {
                        throw new Error(response.error || '删除失败');
                    }
                })
                .catch(error => {
                    console.error('删除历史任务失败:', error);
                    showNotification(`删除失败: ${error.message}`, 'danger');
                })
                .finally(() => {
                    // 恢复按钮状态
                    if (deleteBtn) {
                        deleteBtn.innerHTML = originalText;
                        deleteBtn.disabled = false;
                    }
                });
        }
    };
    
    // 配置预设管理
    const PresetManager = {
        currentPresets: [],
        
        // 显示预设模态框
        showModal: function() {
            $('#presetModal').modal('show');
            this.loadPresets();
        },
        
        // 加载预设
        loadPresets: function() {
            $('#presetList').html(`
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                </div>
            `);
            
            API.get('/api/config/presets')
                .then(response => {
                    if (response.success) {
                        this.currentPresets = response.data;
                        this.renderPresets(response.data);
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('加载配置预设失败:', error);
                    $('#presetList').html(`
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            加载配置预设失败: ${error.message}
                        </div>
                    `);
                });
        },
        
        // 渲染预设列表
        renderPresets: function(presets) {
            if (!presets || presets.length === 0) {
                $('#presetList').html(`
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-bookmark fa-3x mb-3"></i>
                        <p>暂无配置预设</p>
                        <p class="small">使用右上角的"保存预设"按钮来保存当前配置</p>
                    </div>
                `);
                return;
            }
            
            let html = '<div class="list-group">';
            
            presets.forEach(preset => {
                const config = preset.config || {};
                const createdTime = new Date(preset.created_at).toLocaleString('zh-CN');
                
                html += `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <div class="flex-grow-1">
                                <h6 class="mb-1">
                                    <i class="fas fa-bookmark me-1"></i>
                                    ${this.escapeHtml(preset.name)}
                                </h6>
                                <p class="mb-1 text-muted small">
                                    ${preset.description ? this.escapeHtml(preset.description) : '无描述'}
                                </p>
                                <small class="text-muted">
                                    <i class="fas fa-clock me-1"></i>创建时间: ${createdTime}
                                    <span class="ms-2"><i class="fas fa-search me-1"></i>查询: ${this.escapeHtml(config.search_query || '未知')}</span>
                                </small>
                            </div>
                            <div class="text-end">
                                <div class="btn-group btn-group-sm">
                                    <button class="btn btn-outline-primary" onclick="PresetManager.loadPreset('${preset.id}')">
                                        <i class="fas fa-download me-1"></i>加载
                                    </button>
                                    <button class="btn btn-outline-danger" onclick="PresetManager.deletePreset('${preset.id}', '${this.escapeHtml(preset.name)}')">
                                        <i class="fas fa-trash me-1"></i>删除
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            $('#presetList').html(html);
        },
        
        // 转义HTML
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        // 加载预设
        loadPreset: function(presetId) {
            const preset = this.currentPresets.find(p => p.id === presetId);
            if (!preset) {
                showNotification('预设不存在', 'danger');
                return;
            }
            
            HistoryTaskManager.fillConfigForm(preset.config);
            
            // 修复可访问性问题：在隐藏模态框前清除焦点
            if (document.activeElement) {
                document.activeElement.blur();
            }
            
            // 隐藏模态框，并在完成后设置合适的焦点
            const modal = $('#presetModal');
            modal.one('hidden.bs.modal', function() {
                // 将焦点设置到第一个表单输入字段，提供更好的用户体验
                $('#search_query').focus();
            });
            modal.modal('hide');
            
            showNotification('预设配置已加载成功', 'success');
        },
        
        // 删除预设
        deletePreset: function(presetId, presetName) {
            if (!confirm(`确定要删除预设"${presetName}"吗？此操作不可撤销。`)) {
                return;
            }
            
            API.delete(`/api/config/presets/${presetId}`)
                .then(response => {
                    if (response.success) {
                        showNotification('预设删除成功', 'success');
                        this.loadPresets(); // 重新加载列表
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('删除预设失败:', error);
                    showNotification(`删除预设失败: ${error.message}`, 'danger');
                });
        },
        
        // 显示保存预设模态框
        showSaveModal: function() {
            $('#presetName').val('');
            $('#presetDescription').val('');
            $('#savePresetModal').modal('show');
        },
        
        // 保存预设
        savePreset: function() {
            const name = $('#presetName').val().trim();
            const description = $('#presetDescription').val().trim();
            
            if (!name) {
                showNotification('请输入预设名称', 'warning');
                return;
            }
            
            // 获取当前表单配置
            const config = this.getCurrentConfig();
            
            const data = {
                name: name,
                description: description,
                config: config
            };
            
            API.post('/api/config/presets', data)
                .then(response => {
                    if (response.success) {
                        // 修复可访问性问题：在隐藏模态框前清除焦点
                        if (document.activeElement) {
                            document.activeElement.blur();
                        }
                        
                        $('#savePresetModal').modal('hide');
                        showNotification('预设保存成功', 'success');
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('保存预设失败:', error);
                    showNotification(`保存预设失败: ${error.message}`, 'danger');
                });
        },
        
        // 获取当前表单配置
        getCurrentConfig: function() {
            const config = {
                search_query: $('#search_query').val() || '',
                user_requirements: $('#user_requirements').val() || '',
                task_name: $('#task_name').val() || '',
                llm_model_name: $('#llm_model_name').val() || '',
                abstract_analysis_model: $('#abstract_analysis_model').val() || '',
                full_paper_analysis_model: $('#full_paper_analysis_model').val() || '',
                deep_analysis_model: $('#deep_analysis_model').val() || '',
                vision_model: $('#vision_model').val() || '',
                max_papers_per_search: parseInt($('#max_papers_per_search').val()) || 20,
                relevance_threshold: parseFloat($('#relevance_threshold').val()) || 0.7,
                deep_analysis_threshold: parseFloat($('#deep_analysis_threshold').val()) || 0.8,
                search_mode: $('#search_mode').val() || 'latest',
                ocr_char_limit_for_analysis: parseInt($('#ocr_char_limit_for_analysis').val()) || 10000,
                enable_deep_analysis: $('#enable_deep_analysis').is(':checked')
            };
            
            // 添加定时任务配置
            if ($('input[name="execution_mode"]:checked').val() === 'scheduled') {
                config.interval_seconds = parseInt($('#interval_seconds').val()) || 3600;
            }
            
            // 添加搜索模式相关配置
            const searchMode = $('#search_mode').val();
            if (searchMode === 'date_range') {
                config.start_year = parseInt($('#start_year').val()) || null;
                config.end_year = parseInt($('#end_year').val()) || null;
            } else if (searchMode === 'after_year') {
                config.after_year = parseInt($('#after_year').val()) || null;
            }
            
            return config;
        }
    };
    
    // 事件绑定
    $('#loadHistoryTaskBtn').click(function() {
        HistoryTaskManager.showModal();
    });
    
    $('#loadPresetBtn').click(function() {
        PresetManager.showModal();
    });
    
    $('#savePresetBtn').click(function() {
        PresetManager.showSaveModal();
    });
    
    $('#confirmSavePresetBtn').click(function() {
        PresetManager.savePreset();
    });
    
    $('#refreshHistoryBtn').click(function() {
        HistoryTaskManager.loadHistoryTasks();
    });
    
    $('#historyStatusFilter').change(function() {
        HistoryTaskManager.loadHistoryTasks();
    });
    
    $('#historySearchInput').on('input', debounce(function(event) {
        HistoryTaskManager.renderHistoryTasks(HistoryTaskManager.currentTasks, $(event.target).val());
    }, 300));
    
    // 编辑模态框的阈值滑块事件
    $('#edit_relevance_threshold').on('input', function() {
        $('#edit_relevance_threshold_value').text(($(this).val() * 100).toFixed(0) + '%');
    });
    
    $('#edit_summarization_threshold').on('input', function() {
        $('#edit_summarization_threshold_value').text(($(this).val() * 100).toFixed(0) + '%');
    });
    
    // 编辑模态框的搜索模式变化事件
    $('#edit_search_mode').on('change', function() {
        HistoryTaskManager.updateEditSearchModeFields($(this).val());
    });
    
    // 全局暴露管理器
    window.HistoryTaskManager = HistoryTaskManager;
    window.PresetManager = PresetManager;
});