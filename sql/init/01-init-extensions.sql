-- 初始化PostgreSQL扩展
-- 启用UUID生成扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 启用随机UUID生成（PostgreSQL 13+）
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 创建数据库用户和权限设置
DO $$
BEGIN
    -- 确保用户存在
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'homesystem') THEN
        CREATE USER homesystem WITH PASSWORD 'homesystem123';
    END IF;
    
    -- 授予权限
    GRANT ALL PRIVILEGES ON DATABASE homesystem TO homesystem;
    GRANT ALL ON SCHEMA public TO homesystem;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO homesystem;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO homesystem;
    
    -- 设置默认权限
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO homesystem;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO homesystem;
END
$$;