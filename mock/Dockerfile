FROM python:3.12-slim
WORKDIR /app
COPY mock/server.py .
COPY ui-mockup /app/ui-mockup
ENV UI_DIR=/app/ui-mockup
USER nobody
EXPOSE 8080
CMD ["python", "-u", "server.py"]
