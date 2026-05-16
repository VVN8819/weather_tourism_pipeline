import requests
import time
from dotenv import load_dotenv
import os
import json
from pathlib import Path
from datetime import datetime

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
def collect_weather_data(city: str) -> dict | None:
    
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
            weather_data["_metadata'"] = {
            "collection_time": datetime.now().isoformat(),
            "source": "openweathermap.org",
            "city_query": city
            }
            return weather_data
        elif response.status_code == 429:
            print(f'{city}: Лимит запросов (429). Ждём 60 сек.')
            return collect_weather_data(city) # повторяем
        else:
            print(f'{city}: Неожиданная ошибка {response.status_code} — {response.text}')
        
    except requests.exceptions.RequestException as e:
        print(f'{city}: Ошибка - {e}')
    
    print(f'Ответ: {city} - {response}')
    return None

# Сохраняет сырые JSON-данные в файл с таймстампом
def save_raw_data(data: dict, city: str, folder: Path):
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f'{city.lower()}_{timestamp}.json'
    filepath = folder / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f'Сохранено: {filepath}')

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
    print(f'Папка для сохранения: {output_folder}')
    
    # Перебираем города
    for city in cities:
        data = collect_weather_data(city)
        
        if data:
            save_raw_data(data, city, output_folder)
        else:
            print(f'Не удалось получить данные для {city}')
        
        if city != cities[-1]:
            print(f'Пауза {delay_time} сек перед следующим запросом.\n')
            time.sleep(delay_time)
        
    print('\nГотово!')

# запуск
if __name__ == "__main__":
    main()