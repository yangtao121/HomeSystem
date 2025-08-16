#!/bin/bash

# HomeSystem Port Checker Script
# 检查所有必需端口的可用性

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认端口列表
CORE_PORTS=(15432 16379 5001 5002)
OPTIONAL_PORTS=(8080 8081 80 9090 3000 443)

# 帮助信息
show_help() {
    echo "HomeSystem 端口检查工具"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -c, --core-only     仅检查核心端口 (15432, 16379, 5001, 5002)"
    echo "  -a, --all          检查所有端口（包括可选服务）"
    echo "  -p, --port PORT    检查指定端口"
    echo "  -l, --list         列出所有默认端口"
    echo "  -f, --fix          显示端口冲突解决建议"
    echo "  -v, --verbose      详细输出"
    echo "  -h, --help         显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                 # 检查核心端口"
    echo "  $0 -a              # 检查所有端口"
    echo "  $0 -p 8080         # 检查指定端口"
    echo "  $0 -f              # 显示解决建议"
}

# 列出端口信息
list_ports() {
    echo -e "${BLUE}=== HomeSystem 默认端口映射 ===${NC}"
    echo ""
    echo -e "${YELLOW}核心服务端口:${NC}"
    echo "  15432 - PostgreSQL (数据库)"
    echo "  16379 - Redis (缓存)"
    echo "  5001  - OCR Service (OCR处理)"
    echo "  5002  - PaperAnalysis (Web应用)"
    echo ""
    echo -e "${YELLOW}可选服务端口:${NC}"
    echo "  8080  - pgAdmin (数据库管理)"
    echo "  8081  - Redis Commander (Redis管理)"
    echo "  80    - Nginx (代理服务)"
    echo "  443   - Nginx SSL (HTTPS代理)"
    echo "  9090  - Prometheus (监控)"
    echo "  3000  - Grafana (仪表板)"
}

# 检查单个端口
check_port() {
    local port=$1
    local verbose=${2:-false}
    
    if command -v lsof >/dev/null 2>&1; then
        local result=$(lsof -i :$port 2>/dev/null)
        if [ -n "$result" ]; then
            echo -e "${RED}✗${NC} 端口 $port 被占用"
            if [ "$verbose" = true ]; then
                echo "$result" | head -n 5
            fi
            return 1
        else
            echo -e "${GREEN}✓${NC} 端口 $port 可用"
            return 0
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            echo -e "${RED}✗${NC} 端口 $port 被占用"
            if [ "$verbose" = true ]; then
                netstat -tlnp 2>/dev/null | grep ":$port "
            fi
            return 1
        else
            echo -e "${GREEN}✓${NC} 端口 $port 可用"
            return 0
        fi
    elif command -v ss >/dev/null 2>&1; then
        if ss -tlnp 2>/dev/null | grep -q ":$port "; then
            echo -e "${RED}✗${NC} 端口 $port 被占用"
            if [ "$verbose" = true ]; then
                ss -tlnp 2>/dev/null | grep ":$port "
            fi
            return 1
        else
            echo -e "${GREEN}✓${NC} 端口 $port 可用"
            return 0
        fi
    else
        echo -e "${YELLOW}⚠${NC} 无法检查端口 $port (未找到 lsof/netstat/ss 命令)"
        return 2
    fi
}

# 显示修复建议
show_fix_suggestions() {
    echo -e "${BLUE}=== 端口冲突解决方案 ===${NC}"
    echo ""
    echo -e "${YELLOW}方案1: 修改环境变量 (推荐)${NC}"
    echo "  # 数据库模块"
    echo "  echo 'DB_PORT=25432' >> database/.env"
    echo "  echo 'REDIS_PORT=26379' >> database/.env"
    echo ""
    echo "  # OCR模块"
    echo "  echo 'OCR_SERVICE_PORT=8080' >> remote_app/.env"
    echo ""
    echo "  # Web模块"
    echo "  echo 'FLASK_PORT=8002' >> Web/PaperAnalysis/.env"
    echo ""
    echo -e "${YELLOW}方案2: 停止占用端口的服务${NC}"
    echo "  # 查找占用进程"
    echo "  lsof -i :<端口号>"
    echo "  # 停止进程 (谨慎使用)"
    echo "  sudo kill -9 <PID>"
    echo ""
    echo -e "${YELLOW}方案3: 修改docker-compose.yml${NC}"
    echo "  # 编辑相应模块的docker-compose.yml文件"
    echo "  # 修改端口映射: '25432:5432' (主机端口:容器端口)"
}

# 主函数
main() {
    local check_all=false
    local core_only=true
    local show_fixes=false
    local verbose=false
    local specific_port=""
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--all)
                check_all=true
                core_only=false
                shift
                ;;
            -c|--core-only)
                core_only=true
                check_all=false
                shift
                ;;
            -p|--port)
                specific_port="$2"
                shift 2
                ;;
            -l|--list)
                list_ports
                exit 0
                ;;
            -f|--fix)
                show_fixes=true
                shift
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo -e "${BLUE}=== HomeSystem 端口检查工具 ===${NC}"
    echo ""
    
    # 检查特定端口
    if [ -n "$specific_port" ]; then
        echo "检查端口: $specific_port"
        check_port "$specific_port" "$verbose"
        exit $?
    fi
    
    # 显示修复建议
    if [ "$show_fixes" = true ]; then
        show_fix_suggestions
        exit 0
    fi
    
    # 检查端口
    local failed_ports=()
    local ports_to_check=()
    
    if [ "$check_all" = true ]; then
        ports_to_check=("${CORE_PORTS[@]}" "${OPTIONAL_PORTS[@]}")
        echo "检查所有端口..."
    else
        ports_to_check=("${CORE_PORTS[@]}")
        echo "检查核心端口..."
    fi
    
    echo ""
    
    for port in "${ports_to_check[@]}"; do
        if ! check_port "$port" "$verbose"; then
            failed_ports+=("$port")
        fi
    done
    
    echo ""
    
    # 总结
    if [ ${#failed_ports[@]} -eq 0 ]; then
        echo -e "${GREEN}🎉 所有检查的端口都可用！${NC}"
        echo "您可以继续部署 HomeSystem。"
    else
        echo -e "${RED}❌ 发现 ${#failed_ports[@]} 个端口冲突:${NC} ${failed_ports[*]}"
        echo ""
        echo -e "${YELLOW}解决方案:${NC}"
        echo "1. 运行 '$0 -f' 查看详细解决建议"
        echo "2. 修改环境变量使用其他端口"
        echo "3. 停止占用端口的服务"
        exit 1
    fi
}

# 运行主函数
main "$@"