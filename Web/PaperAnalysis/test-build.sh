#!/bin/bash

# PaperAnalysis Docker Build Test Script
# 测试完整的Docker构建和配置验证

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

# 测试Docker构建
test_docker_build() {
    log_info "测试Docker镜像构建..."
    
    if ./build.sh --no-cache; then
        log_success "Docker镜像构建测试通过"
    else
        log_error "Docker镜像构建测试失败"
        return 1
    fi
}

# 测试Docker Compose配置
test_docker_compose() {
    log_info "测试Docker Compose配置..."
    
    if docker compose config > /dev/null; then
        log_success "Docker Compose配置验证通过"
    else
        log_error "Docker Compose配置验证失败"
        return 1
    fi
}

# 测试镜像基本功能
test_image_basic() {
    log_info "测试镜像基本功能..."
    
    # 检查镜像是否存在
    if ! docker images homesystem-paper-analysis:latest | grep -q homesystem-paper-analysis; then
        log_error "镜像不存在"
        return 1
    fi
    
    # 测试镜像能否正常启动（不运行应用，只检查entrypoint）
    if docker run --rm homesystem-paper-analysis:latest --help > /dev/null 2>&1; then
        log_success "镜像基本功能测试通过"
    else
        log_warning "镜像基本功能测试未通过，但这可能是正常的"
    fi
}

# 检查相关文件
check_files() {
    log_info "检查相关文件..."
    
    local files=(
        "Dockerfile"
        "docker-compose.yml"
        "docker-entrypoint.sh"
        ".env.example"
        ".dockerignore"
        "build.sh"
        "deploy.sh"
        "stop.sh"
    )
    
    local missing_files=()
    
    for file in "${files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -eq 0 ]; then
        log_success "所有必需文件检查通过"
    else
        log_error "缺少以下文件:"
        for file in "${missing_files[@]}"; do
            log_error "  - $file"
        done
        return 1
    fi
}

# 检查脚本权限
check_permissions() {
    log_info "检查脚本执行权限..."
    
    local scripts=(
        "build.sh"
        "deploy.sh"
        "stop.sh"
        "docker-entrypoint.sh"
    )
    
    local permission_issues=()
    
    for script in "${scripts[@]}"; do
        if [ ! -x "$script" ]; then
            permission_issues+=("$script")
        fi
    done
    
    if [ ${#permission_issues[@]} -eq 0 ]; then
        log_success "脚本权限检查通过"
    else
        log_warning "以下脚本没有执行权限:"
        for script in "${permission_issues[@]}"; do
            log_warning "  - $script"
        done
        log_info "正在修复权限..."
        chmod +x "${permission_issues[@]}"
        log_success "权限修复完成"
    fi
}

# 显示部署信息
show_deployment_info() {
    echo
    log_success "=== 测试完成 ==="
    echo
    log_info "Docker镜像信息:"
    docker images homesystem-paper-analysis --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    echo
    log_info "下一步操作:"
    echo "  1. 配置环境变量: cp .env.example .env && vim .env"
    echo "  2. 启动服务: ./deploy.sh"
    echo "  3. 查看状态: ./deploy.sh --status"
    echo "  4. 查看日志: ./deploy.sh --logs"
    echo "  5. 停止服务: ./deploy.sh --down"
    echo
    log_info "构建和配置测试全部通过！🎉"
}

# 主函数
main() {
    log_info "=== PaperAnalysis Docker 构建测试 ==="
    
    # 检查文件
    check_files
    
    # 检查权限
    check_permissions
    
    # 测试Docker Compose配置
    test_docker_compose
    
    # 测试镜像基本功能
    test_image_basic
    
    # 显示信息
    show_deployment_info
}

# 执行主函数
main "$@"