# Course Content Studio — MCP server (the "decoupling" unit).
#
# IMPORTANT: build context is the PARENT course-content-studio/ directory, so
# this image can include the shared lib/ package the tools call into:
#
#   docker build -f mcp-server/Dockerfile -t genai-course-mcp .   # run from course-content-studio/
#
FROM python:3.11-slim

WORKDIR /app

# so `from lib import ...` resolves to the copied package
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Install deps first for better layer caching.
COPY mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared library the tools delegate to (vectors + db + config).
COPY lib/ ./lib/

# The MCP server itself.
COPY mcp-server/server.py .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "echo '(c) Dr. Tim Smith, 2026' && python server.py"]
