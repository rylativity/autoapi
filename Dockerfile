FROM python:3
ENV PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/* /app/src/
WORKDIR /app/src
CMD ["uvicorn", "app:app", "--reload", "--log-level", "debug", "--host", "0.0.0.0"]
