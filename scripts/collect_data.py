import requests
import time
from dotenv import load_dotenv
import os

# Загружает API из файла .env
load_dotenv()
api_key = os.getenv("openweather_api_key")

# Переменные для запроса
base_url = "http://api.openweathermap.org/data/2.5/weather"
cities = ["Moscow", "Saint Petersburg"]

# Переменные для ожидания
delay_time = 1.5

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
        elif response.status_code == 429:
            print(f'{city}: Лимит запросов (429). Ждём 60 сек.')
            return collect_weather_data(city) # повторяем
        else:
            print(f'{city}: Неожиданная ошибка {response.status_code} — {response.text}')
        
    except requests.exceptions.RequestException as e:
        print(f'{city}: Ошибка - {e}')
    
    print(f'Ответ: {city} - {response}')

# Главная функция:
# - запрос в collect_weather_data
def main():
    # Наличие API ключа
    if not api_key:
        print('Ошибка: Не найден API-ключ в переменной openweather_api_key. Проверьте файл .env.')
        return
    
    # Перебираем города
    for city in cities:
        data = collect_weather_data(city)
        
        if city != cities[-1]:
            print(f'Пауза {delay_time} сек перед следующим запросом.\n')
            time.sleep(delay_time)
        
    print('\nГотово!')

# запуск
if __name__ == "__main__":
    main()