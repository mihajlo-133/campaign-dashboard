FROM python:3.12-slim
ARG CACHEBUST=1
COPY gtm/prospeqt-outreach-dashboard/server.py .
COPY gtm/prospeqt-outreach-dashboard/templates/ ./templates/
CMD ["python", "server.py"]
