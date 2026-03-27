FROM python:3.12-slim
WORKDIR /app
COPY client_dashboard.py .
CMD ["python", "client_dashboard.py"]
