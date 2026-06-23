FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r istv && useradd -r -g istv -d /app -s /sbin/nologin istv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R istv:istv /app

USER istv

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
