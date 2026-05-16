import requests
import time
from dotenv import load_dotenv
import os
import json
from pathlib import Path
from datetime import datetime
import logging

# ============== Логирование  ===================
def setup_logger(log_folder: Path) -> logging.Logger:
    
    logger = logging.getLogger("weather_pipeline")
    logger.setLevel(logging.INFO)
    
    # Очищаем старые handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # сообщение
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # сохраняем Лог в файл
    file_handler = logging.FileHandler(
        log_folder / "collection_log.txt",
        mode="a",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Лог в консоль (для удобства отладки)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Загружает API из файла .env
load_dotenv()
api_key = os.getenv("openweather_api_key")

# Переменные для запроса
base_url = "https://api.openweathermap.org/data/2.5/weather"
cities = ["Moscow", "Saint Petersburg", "Sochi", "Kazan", "Novosibirsk"]

# Переменные для ожидания
delay_time = 1.5

# Переменные для сохранения
output_dir = Path("data/raw/openweather_api")

# Создаёт папку с датами
def create_date_folder():
    
    today = datetime.now()
    data_dir = output_dir / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
    

# Запрос по API для города. Возврат словаря с данными
def collect_weather_data(city: str, logger: logging.Logger) -> dict | None:
    
    url_params_dict = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "ru"
    }
    
    try:
        response = requests.get(base_url, params=url_params_dict, timeout=10)
        
        if response.status_code == 200:
            weather_data = response.json()
            
            # Добавляем метаданные
            weather_data["_metadata"] = {
            "collection_time": datetime.now().isoformat(),
            "source": "openweathermap.org",
            "city_query": city
            }
            logger.info(f'{city}: Данные получены (200)')
            return weather_data
        elif response.status_code == 429:
            logger.warning(f'{city}: Лимит запросов (429). Ждём 60 сек.')
            time.sleep(60)
            return collect_weather_data(city, logger) # повторяем
        else:
            logger.error(f'{city}: Неожиданная ошибка {response.status_code} — {response.text}')
        
    except requests.exceptions.RequestException as e:
        logger.error(f'{city}: Ошибка - {type(e).__name__}: {e}')
    
    return None

# Сохраняет сырые JSON-данные в файл с таймстампом
def save_raw_data(data: dict, city: str, folder: Path, logger: logging.Logger):
    
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f'{city.lower().replace(" ", "_")}_{timestamp}.json'
    filepath = folder / filename
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f'{city}: Сохранено в {filepath}')
    except IOError as e:
        logger.error(f'{city}: Не удалось сохранить файл — {e}')

# Главная функция:
# - запрос в collect_weather_data
# - запрос в create_date_folder
# - запрос в save_raw_data
def main():
    # Наличие API ключа
    if not api_key:
        print('Ошибка: Не найден API-ключ в переменной openweather_api_key. Проверьте файл .env.')
        return
    
    # Папка для сохранения:
    output_folder = create_date_folder()
    # вызов логирования
    logger = setup_logger(output_folder)
    logger.info(f'Папка для сохранения: {output_folder}')
    
    # Перебираем города
    for city in cities:
        data = collect_weather_data(city, logger)
        
        if data:
            save_raw_data(data, city, output_folder, logger)
        else:
            logger.warning(f'Не удалось получить данные для {city}')
        
        if city != cities[-1]:
            logger.info(f'Пауза {delay_time} сек перед следующим запросом.\n')
            time.sleep(delay_time)
        
    logger.info('\nГотово!')
    print(f"\nЛог сохранён в: {output_folder / 'collection_log.txt'}")

# запуск
if __name__ == "__main__":
    main()