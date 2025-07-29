// PaperGather Main JavaScript

$(document).ready(function() {
    // 初始化工具提示
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // 自动隐藏alert
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);
    
    // 为所有卡片添加淡入动画
    $('.card').addClass('fade-in');
});

// 通用工具函数
const Utils = {
    // 显示通知
    showNotification: function(message, type = 'info', duration = 5000) {
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        $('main .container-fluid').prepend(alertHtml);
        
        // 自动隐藏
        if (duration > 0) {
            setTimeout(function() {
                $('.alert').first().alert('close');
            }, duration);
        }
    },
    
    // 格式化日期
    formatDate: function(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    // 格式化持续时间
    formatDuration: function(seconds) {
        if (!seconds) return '0秒';
        
        if (seconds < 60) {
            return seconds.toFixed(1) + '秒';
        } else if (seconds < 3600) {
            return (seconds / 60).toFixed(1) + '分钟';
        } else {
            return (seconds / 3600).toFixed(1) + '小时';
        }
    },
    
    // 格式化文件大小
    formatFileSize: function(bytes) {
        if (!bytes) return '0 B';
        
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
    },
    
    // 防抖函数
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // 节流函数
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    },
    
    // 复制到剪贴板
    copyToClipboard: function(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                this.showNotification('已复制到剪贴板', 'success', 2000);
            });
        } else {
            // 兼容旧浏览器
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showNotification('已复制到剪贴板', 'success', 2000);
        }
    },
    
    // 获取状态徽章类
    getStatusBadgeClass: function(status) {
        const statusMap = {
            'pending': 'warning',
            'running': 'info',
            'completed': 'success',
            'failed': 'danger',
            'stopped': 'secondary'
        };
        return statusMap[status] || 'secondary';
    }
};

// API 工具类
const API = {
    // 基础请求方法
    request: function(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        return fetch(url, finalOptions)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error('API request failed:', error);
                throw error;
            });
    },
    
    // GET 请求
    get: function(url) {
        return this.request(url);
    },
    
    // POST 请求
    post: function(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // PUT 请求
    put: function(url, data) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // DELETE 请求
    delete: function(url) {
        return this.request(url, {
            method: 'DELETE'
        });
    }
};

// 任务管理类
const TaskManager = {
    // 轮询任务状态
    pollTaskStatus: function(taskId, callback, interval = 3000) {
        const poll = () => {
            API.get(`/api/task/status/${taskId}`)
                .then(response => {
                    if (response.success) {
                        const shouldContinue = callback(response.data);
                        
                        // 如果任务完成或失败，停止轮询
                        if (shouldContinue && 
                            !['completed', 'failed', 'stopped'].includes(response.data.status)) {
                            setTimeout(poll, interval);
                        }
                    }
                })
                .catch(error => {
                    console.error('Poll task status failed:', error);
                    callback(null);
                });
        };
        
        poll();
    },
    
    // 取消任务
    cancelTask: function(taskId) {
        return API.post(`/task/cancel/${taskId}`, {});
    },
    
    // 停止定时任务
    stopScheduledTask: function(taskId) {
        return API.post(`/task/stop_scheduled/${taskId}`, {});
    }
};

// 数据可视化工具
const Charts = {
    // 创建简单的进度圆环
    createProgressRing: function(elementId, progress, size = 100) {
        const svg = d3.select(`#${elementId}`)
            .append('svg')
            .attr('width', size)
            .attr('height', size);
        
        const radius = size / 2 - 10;
        const arc = d3.arc()
            .innerRadius(radius - 10)
            .outerRadius(radius)
            .startAngle(0)
            .endAngle(2 * Math.PI * progress);
        
        svg.append('path')
            .attr('d', arc)
            .attr('transform', `translate(${size/2}, ${size/2})`)
            .attr('fill', '#007bff');
    }
};

// 表单验证工具
const FormValidator = {
    // 验证必需字段
    validateRequired: function(value, fieldName) {
        if (!value || value.trim() === '') {
            return `${fieldName} 不能为空`;
        }
        return null;
    },
    
    // 验证数字范围
    validateRange: function(value, min, max, fieldName) {
        const num = parseFloat(value);
        if (isNaN(num)) {
            return `${fieldName} 必须是数字`;
        }
        if (num < min || num > max) {
            return `${fieldName} 必须在 ${min} - ${max} 范围内`;
        }
        return null;
    },
    
    // 验证邮箱
    validateEmail: function(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            return '邮箱格式不正确';
        }
        return null;
    }
};

// 本地存储工具
const Storage = {
    // 设置项
    set: function(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error('Storage set failed:', error);
        }
    },
    
    // 获取项
    get: function(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
            console.error('Storage get failed:', error);
            return defaultValue;
        }
    },
    
    // 删除项
    remove: function(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error('Storage remove failed:', error);
        }
    },
    
    // 清空存储
    clear: function() {
        try {
            localStorage.clear();
        } catch (error) {
            console.error('Storage clear failed:', error);
        }
    }
};

// 导出功能
const Exporter = {
    // 导出为 JSON
    exportJSON: function(data, filename = 'export.json') {
        const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data, null, 2));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute('href', dataStr);
        downloadAnchorNode.setAttribute('download', filename);
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    },
    
    // 导出为 CSV
    exportCSV: function(data, filename = 'export.csv') {
        if (!data || data.length === 0) return;
        
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(header => {
                const cell = row[header] || '';
                return typeof cell === 'string' && cell.includes(',') ? `"${cell}"` : cell;
            }).join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
};

// 全局对象暴露
window.PaperGather = {
    Utils,
    API,
    TaskManager,
    Charts,
    FormValidator,
    Storage,
    Exporter
};