# Образ = Python + бібліотеки + наш код, запаковані разом.
# Однаково працює на Mac, на сервері і в GitHub Actions.
FROM python:3.12-slim

WORKDIR /app

# Спершу лише залежності: Docker запам'ятовує цей шар і не перевстановлює
# бібліотеки, якщо змінився тільки код.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# База лежить у /data — це папка-том, яка живе ПОЗА контейнером
ENV DB_PATH=/data/data.db
EXPOSE 8000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "--access-logfile", "-", "app:app"]
