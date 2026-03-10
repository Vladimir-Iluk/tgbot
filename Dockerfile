FROM python:3.11-slim-buster

# Налаштування середовища для виводу логів без затримок
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/src/app

# Копіюємо та встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проекту
COPY . .

# Команда запуску за замовчуванням
CMD ["python", "bot.py"]