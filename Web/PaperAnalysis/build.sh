#!/bin/bash

# PaperAnalysis Docker Build Script
# 构建PaperAnalysis Docker镜像

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
IMAGE_NAME="homesystem-paper-analysis"
IMAGE_TAG="latest"
BUILD_ARGS=""
NO_CACHE=false
PUSH_IMAGE=false
REGISTRY=""

# 帮助信息
show_help() {
    cat << EOF
PaperAnalysis Docker Build Script

用法: $0 [选项]

选项:
    -t, --tag TAG        设置镜像标签 (默认: latest)
    -n, --name NAME      设置镜像名称 (默认: homesystem-paper-analysis)
    -r, --registry REG   设置镜像仓库地址
    --no-cache          不使用构建缓存
    --push              构建完成后推送到仓库
    --build-arg ARG     传递构建参数 (可多次使用)
    -h, --help          显示此帮助信息

示例:
    $0                                    # 基本构建
    $0 -t v1.0                           # 指定标签
    $0 -t v1.0 --push                    # 构建并推送
    $0 -r registry.example.com -t v1.0   # 指定仓库地址
    $0 --no-cache                        # 强制重新构建
    $0 --build-arg HTTP_PROXY=http://proxy:8080  # 设置代理

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -n|--name)
                IMAGE_NAME="$2"
                shift 2
                ;;
            -r|--registry)
                REGISTRY="$2"
                shift 2
                ;;
            --no-cache)
                NO_CACHE=true
                shift
                ;;
            --push)
                PUSH_IMAGE=true
                shift
                ;;
            --build-arg)
                BUILD_ARGS="$BUILD_ARGS --build-arg $2"
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
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不在PATH中"
        exit 1
    fi
    
    # 检查Docker是否运行
    if ! docker info &> /dev/null; then
        log_error "Docker 服务未运行"
        exit 1
    fi
    
    # 检查必要文件 - 需要检查相对于根目录的路径
    local required_files=(
        "Web/PaperAnalysis/Dockerfile"
        "Web/PaperAnalysis/requirements.txt"
        "Web/PaperAnalysis/app.py"
        "Web/PaperAnalysis/docker-entrypoint.sh"
        "HomeSystem"
    )
    
    # 切换到项目根目录
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local root_dir="$(cd "$script_dir/../.." && pwd)"
    
    pushd "$root_dir" > /dev/null
    
    for file in "${required_files[@]}"; do
        if [ ! -e "$file" ]; then
            log_error "缺少必要文件: $file"
            popd > /dev/null
            exit 1
        fi
    done
    
    log_success "依赖检查通过"
    
    # 返回原目录
    popd > /dev/null
}

# 构建镜像
build_image() {
    log_info "开始构建Docker镜像..."
    
    # 构建完整镜像名称
    local full_image_name="$IMAGE_NAME:$IMAGE_TAG"
    if [ -n "$REGISTRY" ]; then
        full_image_name="$REGISTRY/$full_image_name"
    fi
    
    # 构建参数
    local build_cmd="docker build"
    
    if [ "$NO_CACHE" = true ]; then
        build_cmd="$build_cmd --no-cache"
    fi
    
    if [ -n "$BUILD_ARGS" ]; then
        build_cmd="$build_cmd $BUILD_ARGS"
    fi
    
    # 构建命令需要指定正确的上下文和Dockerfile
    build_cmd="$build_cmd -f Web/PaperAnalysis/Dockerfile -t $full_image_name ."
    
    # 切换到项目根目录执行构建
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local root_dir="$(cd "$script_dir/../.." && pwd)"
    
    log_info "从根目录构建: $root_dir"
    log_info "执行构建命令: $build_cmd"
    
    # 在根目录执行构建
    pushd "$root_dir" > /dev/null
    
    if eval $build_cmd; then
        log_success "镜像构建成功: $full_image_name"
    else
        log_error "镜像构建失败"
        popd > /dev/null
        exit 1
    fi
    
    popd > /dev/null
    
    # 显示镜像信息
    log_info "镜像信息:"
    docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
}

# 推送镜像
push_image() {
    if [ "$PUSH_IMAGE" = true ]; then
        if [ -z "$REGISTRY" ]; then
            log_warning "未指定仓库地址，跳过推送"
            return
        fi
        
        local full_image_name="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
        
        log_info "推送镜像到仓库: $full_image_name"
        
        if docker push "$full_image_name"; then
            log_success "镜像推送成功"
        else
            log_error "镜像推送失败"
            exit 1
        fi
    fi
}

# 清理构建缓存（可选）
cleanup_build_cache() {
    log_info "是否清理Docker构建缓存? [y/N]"
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY])
            log_info "清理Docker构建缓存..."
            docker builder prune -f
            log_success "构建缓存清理完成"
            ;;
        *)
            log_info "跳过清理构建缓存"
            ;;
    esac
}

# 主函数
main() {
    log_info "=== PaperAnalysis Docker 构建脚本 ==="
    
    # 解析参数
    parse_args "$@"
    
    # 检查依赖
    check_dependencies
    
    # 构建镜像
    build_image
    
    # 推送镜像
    push_image
    
    # 构建完成
    log_success "=== 构建完成 ==="
    
    # 显示下一步操作建议
    echo
    log_info "下一步操作建议:"
    echo "  1. 复制 .env.example 为 .env 并配置环境变量"
    echo "  2. 运行 ./deploy.sh 启动服务"
    echo "  3. 或手动运行: docker-compose up -d"
    
    # 询问是否清理缓存
    cleanup_build_cache
}

# 执行主函数
main "$@"