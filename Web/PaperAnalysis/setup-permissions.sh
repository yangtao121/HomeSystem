#!/bin/bash

# PaperAnalysis Permissions Setup Script
# 设置Docker部署所需的目录权限

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取Docker用户ID
DOCKER_UID=1000
DOCKER_GID=1000

# 获取当前用户信息
CURRENT_USER=$(whoami)
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

# 显示帮助信息
show_help() {
    cat << EOF
PaperAnalysis Permissions Setup Script

此脚本将设置Docker部署所需的目录权限。

用法: $0 [选项]

选项:
    --fix           自动修复权限问题
    --check         仅检查权限状态
    --uid UID       指定Docker容器用户ID (默认: 1000)
    --gid GID       指定Docker容器组ID (默认: 1000)
    -h, --help      显示此帮助信息

说明:
    Docker容器内的应用将以用户ID $DOCKER_UID 运行，
    需要确保宿主机上的目录对该用户ID具有读写权限。

EOF
}

# 解析命令行参数
parse_args() {
    local action="check"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --fix)
                action="fix"
                shift
                ;;
            --check)
                action="check"
                shift
                ;;
            --uid)
                DOCKER_UID="$2"
                shift 2
                ;;
            --gid)
                DOCKER_GID="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo "$action"
}

# 检查目录权限
check_directory_permissions() {
    local dir="$1"
    local name="$2"
    
    if [ ! -d "$dir" ]; then
        log_warning "$name 目录不存在: $dir"
        return 1
    fi
    
    # 检查目录是否可写
    if [ -w "$dir" ]; then
        log_success "$name 目录权限正常: $dir"
        return 0
    else
        local dir_uid=$(stat -c "%u" "$dir" 2>/dev/null || echo "unknown")
        local dir_gid=$(stat -c "%g" "$dir" 2>/dev/null || echo "unknown")
        local dir_perm=$(stat -c "%a" "$dir" 2>/dev/null || echo "unknown")
        
        log_warning "$name 目录权限问题: $dir"
        log_info "  当前所有者: UID=$dir_uid, GID=$dir_gid"
        log_info "  当前权限: $dir_perm"
        log_info "  需要权限: UID=$DOCKER_UID 可写"
        return 1
    fi
}

# 修复目录权限
fix_directory_permissions() {
    local dir="$1"
    local name="$2"
    
    log_info "修复 $name 目录权限: $dir"
    
    # 创建目录（如果不存在）
    if [ ! -d "$dir" ]; then
        log_info "创建目录: $dir"
        mkdir -p "$dir"
    fi
    
    # 设置权限
    if [ "$CURRENT_UID" = "0" ]; then
        # 以root身份运行，可以直接chown
        chown -R "$DOCKER_UID:$DOCKER_GID" "$dir"
        chmod -R 755 "$dir"
        log_success "$name 目录权限已修复"
    else
        # 非root用户，尝试不同的方法
        if [ "$CURRENT_UID" = "$DOCKER_UID" ]; then
            # 当前用户ID与Docker用户ID相同
            chmod -R 755 "$dir" 2>/dev/null || {
                log_warning "$name 目录权限修复可能需要sudo权限"
                return 1
            }
            log_success "$name 目录权限已修复"
        else
            # 用户ID不同，需要特殊处理
            log_warning "$name 目录权限需要管理员权限修复"
            log_info "请运行: sudo chown -R $DOCKER_UID:$DOCKER_GID $dir"
            return 1
        fi
    fi
}

# 主检查函数
check_permissions() {
    log_info "检查目录权限..."
    log_info "Docker容器用户: UID=$DOCKER_UID, GID=$DOCKER_GID"
    log_info "当前系统用户: $CURRENT_USER (UID=$CURRENT_UID, GID=$CURRENT_GID)"
    echo
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root="$(cd "$script_dir/../.." && pwd)"
    
    local issues=0
    
    # 检查项目数据目录
    if ! check_directory_permissions "$project_root/data" "项目数据"; then
        issues=$((issues + 1))
    fi
    
    # 检查应用目录
    if ! check_directory_permissions "$script_dir/logs" "应用日志"; then
        issues=$((issues + 1))
    fi
    
    if ! check_directory_permissions "$script_dir/uploads" "上传文件"; then
        issues=$((issues + 1))
    fi
    
    if ! check_directory_permissions "$script_dir/static/uploads" "静态上传"; then
        issues=$((issues + 1))
    fi
    
    echo
    if [ $issues -eq 0 ]; then
        log_success "所有目录权限检查通过"
        return 0
    else
        log_warning "发现 $issues 个权限问题"
        return $issues
    fi
}

# 主修复函数
fix_permissions() {
    log_info "修复目录权限..."
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root="$(cd "$script_dir/../.." && pwd)"
    
    local issues=0
    
    # 修复项目数据目录
    if ! fix_directory_permissions "$project_root/data" "项目数据"; then
        issues=$((issues + 1))
    fi
    
    # 修复应用目录
    if ! fix_directory_permissions "$script_dir/logs" "应用日志"; then
        issues=$((issues + 1))
    fi
    
    if ! fix_directory_permissions "$script_dir/uploads" "上传文件"; then
        issues=$((issues + 1))
    fi
    
    if ! fix_directory_permissions "$script_dir/static/uploads" "静态上传"; then
        issues=$((issues + 1))
    fi
    
    echo
    if [ $issues -eq 0 ]; then
        log_success "所有权限问题已修复"
        return 0
    else
        log_warning "仍有 $issues 个权限问题需要手动处理"
        return $issues
    fi
}

# 显示权限解决方案
show_solutions() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root="$(cd "$script_dir/../.." && pwd)"
    
    echo
    log_info "权限问题解决方案:"
    echo
    echo "方案1: 使用sudo修复权限 (推荐)"
    echo "  sudo chown -R $DOCKER_UID:$DOCKER_GID $project_root/data"
    echo "  sudo chown -R $DOCKER_UID:$DOCKER_GID $script_dir/logs"
    echo "  sudo chown -R $DOCKER_UID:$DOCKER_GID $script_dir/uploads"
    echo "  sudo chown -R $DOCKER_UID:$DOCKER_GID $script_dir/static/uploads"
    echo
    echo "方案2: 自动修复脚本"
    echo "  sudo $0 --fix"
    echo
    echo "方案3: 添加当前用户到docker组 (需要重新登录)"
    echo "  sudo usermod -aG docker $CURRENT_USER"
    echo "  newgrp docker"
    echo
    echo "方案4: 使用ACL设置权限 (如果支持)"
    echo "  sudo setfacl -R -m u:$DOCKER_UID:rwx $project_root/data"
    echo "  sudo setfacl -R -m u:$DOCKER_UID:rwx $script_dir/logs"
    echo "  sudo setfacl -R -m u:$DOCKER_UID:rwx $script_dir/uploads"
    echo "  sudo setfacl -R -m u:$DOCKER_UID:rwx $script_dir/static/uploads"
}

# 主函数
main() {
    log_info "=== PaperAnalysis 权限设置脚本 ==="
    
    local action=$(parse_args "$@")
    
    if [ "$action" = "check" ]; then
        if ! check_permissions; then
            show_solutions
            exit 1
        fi
    elif [ "$action" = "fix" ]; then
        if ! fix_permissions; then
            show_solutions
            exit 1
        fi
        
        # 修复后再次检查
        echo
        check_permissions
    fi
    
    echo
    log_success "权限设置完成！现在可以运行 ./deploy.sh 部署服务"
}

# 执行主函数
main "$@"