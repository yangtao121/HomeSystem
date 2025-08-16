#!/bin/bash

# PaperAnalysis Data Backup Script
# 备份PaperAnalysis相关的数据目录

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

# 默认配置
BACKUP_DIR="./backups"
INCLUDE_LOGS=false
COMPRESS=true
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="paperanalysis_backup_${TIMESTAMP}"

# 帮助信息
show_help() {
    cat << EOF
PaperAnalysis Data Backup Script

用法: $0 [选项]

选项:
    -d, --dir DIR       设置备份目录 (默认: ./backups)
    -n, --name NAME     设置备份文件名前缀 (默认: paperanalysis_backup)
    --include-logs      包含日志文件在备份中
    --no-compress       不压缩备份文件
    -h, --help          显示此帮助信息

示例:
    $0                              # 基本备份
    $0 -d /backup/homesystem        # 指定备份目录
    $0 --include-logs               # 包含日志文件
    $0 -n mybackup                  # 自定义备份名称

备份内容:
    - data/paper_analyze/           # 论文分析结果
    - data/paper_gather/            # 论文收集任务数据
    - uploads/                      # 上传文件
    - static/uploads/               # 静态上传文件
    - 可选: logs/                   # 日志文件 (--include-logs)

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            -n|--name)
                BACKUP_NAME="${2}_${TIMESTAMP}"
                shift 2
                ;;
            --include-logs)
                INCLUDE_LOGS=true
                shift
                ;;
            --no-compress)
                COMPRESS=false
                shift
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
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查tar命令
    if ! command -v tar &> /dev/null; then
        log_error "tar 命令未找到"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 检查数据目录
check_data_directories() {
    log_info "检查数据目录..."
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root="$(cd "$script_dir/../.." && pwd)"
    
    # 要备份的目录
    local data_dirs=(
        "$project_root/data/paper_analyze"
        "$project_root/data/paper_gather"
        "$script_dir/uploads"
        "$script_dir/static/uploads"
    )
    
    if [ "$INCLUDE_LOGS" = true ]; then
        data_dirs+=("$script_dir/logs")
    fi
    
    local missing_dirs=()
    local existing_dirs=()
    
    for dir in "${data_dirs[@]}"; do
        if [ -d "$dir" ]; then
            existing_dirs+=("$dir")
        else
            missing_dirs+=("$dir")
        fi
    done
    
    if [ ${#existing_dirs[@]} -eq 0 ]; then
        log_error "没有找到任何数据目录可备份"
        exit 1
    fi
    
    log_success "找到 ${#existing_dirs[@]} 个目录可备份"
    
    if [ ${#missing_dirs[@]} -gt 0 ]; then
        log_warning "以下目录不存在，将跳过:"
        for dir in "${missing_dirs[@]}"; do
            log_warning "  - $dir"
        done
    fi
}

# 创建备份
create_backup() {
    log_info "开始创建备份..."
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root="$(cd "$script_dir/../.." && pwd)"
    
    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    
    # 准备备份文件路径
    local backup_file="$BACKUP_DIR/$BACKUP_NAME"
    if [ "$COMPRESS" = true ]; then
        backup_file="${backup_file}.tar.gz"
    else
        backup_file="${backup_file}.tar"
    fi
    
    # 准备要备份的路径
    local backup_paths=()
    
    # 数据目录（相对于项目根目录）
    if [ -d "$project_root/data/paper_analyze" ]; then
        backup_paths+=("data/paper_analyze")
    fi
    
    if [ -d "$project_root/data/paper_gather" ]; then
        backup_paths+=("data/paper_gather")
    fi
    
    # PaperAnalysis应用目录（相对于项目根目录）
    if [ -d "$script_dir/uploads" ]; then
        backup_paths+=("Web/PaperAnalysis/uploads")
    fi
    
    if [ -d "$script_dir/static/uploads" ]; then
        backup_paths+=("Web/PaperAnalysis/static/uploads")
    fi
    
    if [ "$INCLUDE_LOGS" = true ] && [ -d "$script_dir/logs" ]; then
        backup_paths+=("Web/PaperAnalysis/logs")
    fi
    
    # 切换到项目根目录
    pushd "$project_root" > /dev/null
    
    # 执行备份
    if [ "$COMPRESS" = true ]; then
        log_info "创建压缩备份: $backup_file"
        tar -czf "$backup_file" "${backup_paths[@]}" 2>/dev/null || {
            log_error "备份创建失败"
            popd > /dev/null
            exit 1
        }
    else
        log_info "创建未压缩备份: $backup_file"
        tar -cf "$backup_file" "${backup_paths[@]}" 2>/dev/null || {
            log_error "备份创建失败"
            popd > /dev/null
            exit 1
        }
    fi
    
    popd > /dev/null
    
    # 检查备份文件
    if [ -f "$backup_file" ]; then
        local file_size=$(du -h "$backup_file" | cut -f1)
        log_success "备份创建成功: $backup_file ($file_size)"
    else
        log_error "备份文件未创建"
        exit 1
    fi
}

# 显示备份信息
show_backup_info() {
    local backup_file="$BACKUP_DIR/$BACKUP_NAME"
    if [ "$COMPRESS" = true ]; then
        backup_file="${backup_file}.tar.gz"
    else
        backup_file="${backup_file}.tar"
    fi
    
    echo
    log_success "=== 备份完成 ==="
    echo
    log_info "备份信息:"
    echo "  - 备份文件: $backup_file"
    echo "  - 备份时间: $(date)"
    echo "  - 文件大小: $(du -h "$backup_file" | cut -f1)"
    echo
    log_info "恢复命令:"
    echo "  cd $(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    if [ "$COMPRESS" = true ]; then
        echo "  tar -xzf $backup_file"
    else
        echo "  tar -xf $backup_file"
    fi
    echo
    log_info "备份内容查看:"
    if [ "$COMPRESS" = true ]; then
        echo "  tar -tzf $backup_file"
    else
        echo "  tar -tf $backup_file"
    fi
}

# 主函数
main() {
    log_info "=== PaperAnalysis 数据备份脚本 ==="
    
    # 解析参数
    parse_args "$@"
    
    # 检查依赖
    check_dependencies
    
    # 检查数据目录
    check_data_directories
    
    # 创建备份
    create_backup
    
    # 显示备份信息
    show_backup_info
}

# 执行主函数
main "$@"