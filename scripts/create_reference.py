import pandas as pd
from pathlib import Path

# Справочник: Федеральный округ
city_federal_district = {
    "Москва": "Центральный ФО",
    "Санкт-Петербург": "Северо-Западный ФО",
    "Сочи": "Южный ФО",
    "Казань": "Приволжский ФО",
    "Новосибирск": "Сибирский ФО"
}

# Справочник: Часовой пояс
city_timezone = {
    "Москва": "UTC+3",
    "Санкт-Петербург": "UTC+3",
    "Сочи": "UTC+3",
    "Казань": "UTC+3",
    "Новосибирск": "UTC+7"
}

# Примерное население города
city_population = {
    "Москва": 13100000,
    "Санкт-Петербург": 5600000,
    "Сочи": 450000,
    "Казань": 1300000,
    "Новосибирск": 1630000
}

# Сезон
tourism_season_dict = {
    "Москва": "Круглогодично",
    "Санкт-Петербург": "Май-Сентябрь",
    "Сочи": "Май-Октябрь",
    "Казань": "Май-Сентябрь",
    "Новосибирск": "Июнь-Август"
}

# Создание простого справочника городов в CSV
def create_city_reference(output_path: Path):
    # Берём ключи из первого словаря (города)
    cities = list(city_federal_district.keys())
    
    df = pd.DataFrame({
        "city": cities,
        "federal_district": [city_federal_district[c] for c in cities],
        "timezone": [city_timezone[c] for c in cities],
        "population": [city_population[c] for c in cities],
        "tourism_season": [tourism_season_dict[c] for c in cities]
    })
    
    # Создаём папку, если нет
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем в CSV
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f'Справочник сохранён: {output_path}')
    print(f'\nПредпросмотр:\n{df}')
    
if __name__ == "__main__":
    
    ref_file = Path("data/enriched/cities_reference.csv")
    create_city_reference(ref_file)