# HomeSystem PostgreSQL Database Image
# Pre-configured with database schema and tables
FROM postgres:15-alpine

# Set environment variables
ENV POSTGRES_DB=homesystem
ENV POSTGRES_USER=homesystem
ENV POSTGRES_PASSWORD=homesystem123
ENV POSTGRES_INITDB_ARGS="--encoding=UTF-8"
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8

# Install additional packages for better functionality
RUN apk add --no-cache \
    tzdata \
    curl \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# Copy initialization scripts
# These will be executed in alphabetical order when the container starts for the first time
COPY init/*.sql /docker-entrypoint-initdb.d/

# Create directories for data persistence
RUN mkdir -p /var/lib/postgresql/data

# Health check to ensure database is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1

# Expose default PostgreSQL port
EXPOSE 5432

# Use the default postgres entrypoint
# It will automatically run the SQL scripts in /docker-entrypoint-initdb.d/