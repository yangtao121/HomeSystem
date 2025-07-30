// PaperGather 配置页面 JavaScript
// 处理历史任务和配置预设功能

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
            
            PaperGather.API.get(`/api/task/history?${params.toString()}`)
                .then(response => {
                    if (response.success) {
                        this.currentTasks = response.data;
                        this.renderHistoryTasks(response.data, searchTerm);
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
                const duration = task.duration ? PaperGather.Utils.formatDuration(task.duration) : '未知';
                
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
            PaperGather.API.get(`/api/task/config/${taskId}`)
                .then(response => {
                    if (response.success) {
                        this.fillConfigForm(response.data);
                        $('#historyTaskModal').modal('hide');
                        PaperGather.Utils.showNotification('配置已加载成功', 'success');
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('加载任务配置失败:', error);
                    PaperGather.Utils.showNotification(`加载配置失败: ${error.message}`, 'danger');
                });
        },
        
        // 填充配置表单
        fillConfigForm: function(config) {
            // 基本配置
            if (config.search_query) $('#search_query').val(config.search_query);
            if (config.user_requirements) $('#user_requirements').val(config.user_requirements);
            if (config.llm_model_name) $('#llm_model_name').val(config.llm_model_name);
            
            // 高级配置
            if (config.max_papers_per_search !== undefined) $('#max_papers_per_search').val(config.max_papers_per_search);
            if (config.relevance_threshold !== undefined) {
                $('#relevance_threshold').val(config.relevance_threshold);
                $('#relevance_threshold_value').text((config.relevance_threshold * 100).toFixed(0) + '%');
            }
            if (config.summarization_threshold !== undefined) {
                $('#summarization_threshold').val(config.summarization_threshold);
                $('#summarization_threshold_value').text((config.summarization_threshold * 100).toFixed(0) + '%');
            }
            
            // 搜索模式
            if (config.search_mode) $('#search_mode').val(config.search_mode);
            
            // 布尔值配置
            if (config.enable_paper_summarization !== undefined) {
                $('#enable_paper_summarization').prop('checked', config.enable_paper_summarization);
            }
            if (config.enable_translation !== undefined) {
                $('#enable_translation').prop('checked', config.enable_translation);
            }
            
            // 定时任务配置
            if (config.interval_seconds && config.interval_seconds > 0) {
                $('#interval_seconds').val(config.interval_seconds);
                // 切换到定时模式
                $('input[name="execution_mode"][value="scheduled"]').prop('checked', true);
                $('.execution-mode-card').removeClass('selected');
                $('.execution-mode-card[data-mode="scheduled"]').addClass('selected');
                $('#scheduled_config').show();
            }
            
            // 触发change事件以更新界面
            $('#search_mode').trigger('change');
        },
        
        // 查看任务详情
        viewTaskDetails: function(taskId) {
            // 在新窗口中打开任务详情页面
            window.open(`/task/result/${taskId}`, '_blank');
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
            
            PaperGather.API.delete(`/api/task/history/${taskId}`)
                .then(response => {
                    if (response.success) {
                        PaperGather.Utils.showNotification('历史任务删除成功', 'success');
                        // 重新加载任务列表
                        this.loadTasks();
                    } else {
                        throw new Error(response.error || '删除失败');
                    }
                })
                .catch(error => {
                    console.error('删除历史任务失败:', error);
                    PaperGather.Utils.showNotification(`删除失败: ${error.message}`, 'danger');
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
            
            PaperGather.API.get('/api/config/presets')
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
                PaperGather.Utils.showNotification('预设不存在', 'danger');
                return;
            }
            
            HistoryTaskManager.fillConfigForm(preset.config);
            $('#presetModal').modal('hide');
            PaperGather.Utils.showNotification('预设配置已加载成功', 'success');
        },
        
        // 删除预设
        deletePreset: function(presetId, presetName) {
            if (!confirm(`确定要删除预设"${presetName}"吗？此操作不可撤销。`)) {
                return;
            }
            
            PaperGather.API.delete(`/api/config/presets/${presetId}`)
                .then(response => {
                    if (response.success) {
                        PaperGather.Utils.showNotification('预设删除成功', 'success');
                        this.loadPresets(); // 重新加载列表
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('删除预设失败:', error);
                    PaperGather.Utils.showNotification(`删除预设失败: ${error.message}`, 'danger');
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
                PaperGather.Utils.showNotification('请输入预设名称', 'warning');
                return;
            }
            
            // 获取当前表单配置
            const config = this.getCurrentConfig();
            
            const data = {
                name: name,
                description: description,
                config: config
            };
            
            PaperGather.API.post('/api/config/presets', data)
                .then(response => {
                    if (response.success) {
                        $('#savePresetModal').modal('hide');
                        PaperGather.Utils.showNotification('预设保存成功', 'success');
                    } else {
                        throw new Error(response.error);
                    }
                })
                .catch(error => {
                    console.error('保存预设失败:', error);
                    PaperGather.Utils.showNotification(`保存预设失败: ${error.message}`, 'danger');
                });
        },
        
        // 获取当前表单配置
        getCurrentConfig: function() {
            const config = {
                search_query: $('#search_query').val() || '',
                user_requirements: $('#user_requirements').val() || '',
                llm_model_name: $('#llm_model_name').val() || '',
                max_papers_per_search: parseInt($('#max_papers_per_search').val()) || 20,
                relevance_threshold: parseFloat($('#relevance_threshold').val()) || 0.7,
                summarization_threshold: parseFloat($('#summarization_threshold').val()) || 0.8,
                search_mode: $('#search_mode').val() || 'latest',
                enable_paper_summarization: $('#enable_paper_summarization').is(':checked'),
                enable_translation: $('#enable_translation').is(':checked')
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
    
    $('#historySearchInput').on('input', PaperGather.Utils.debounce(function() {
        HistoryTaskManager.renderHistoryTasks(HistoryTaskManager.currentTasks, $(this).val());
    }, 300));
    
    // 全局暴露管理器
    window.HistoryTaskManager = HistoryTaskManager;
    window.PresetManager = PresetManager;
});