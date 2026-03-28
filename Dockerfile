FROM python:3.12-slim
ARG CACHEBUST=1
COPY client_dashboard.py .
CMD ["python", "client_dashboard.py"]
