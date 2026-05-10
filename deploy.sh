#!/bin/bash
set -e

# === 阿里云 ECS 一键部署脚本 ===
# 在服务器上 clone 项目后运行此脚本

echo "=== 1. 安装 Docker ==="
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker 已安装"
else
    echo "Docker 已存在，跳过"
fi

if ! command -v docker compose &> /dev/null; then
    echo "安装 docker compose plugin..."
    apt-get update && apt-get install -y docker-compose-plugin
fi

echo "=== 2. 创建 .env 文件 ==="
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# LLM 配置（可选，不填则使用关键词匹配 fallback）
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4o

# 前端 URL（Vercel 部署后的地址，用于 CORS）
CORS_ORIGINS=https://your-project.vercel.app
EOF
    echo "已创建 .env，请编辑填入你的配置："
    echo "  vim .env"
else
    echo ".env 已存在，跳过"
fi

echo "=== 3. 构建并启动后端 ==="
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "=== 部署完成 ==="
echo "后端 API: http://$(curl -s ifconfig.me):8000"
echo "API 文档: http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "下一步："
echo "1. 编辑 .env 填入 LLM_API_KEY 和 CORS_ORIGINS"
echo "2. 重新启动: docker compose -f docker-compose.prod.yml restart"
echo "3. 配置域名和 HTTPS（可选）"
