FROM python:3.12-slim
COPY client_dashboard.py .
CMD ["python", "client_dashboard.py"]
