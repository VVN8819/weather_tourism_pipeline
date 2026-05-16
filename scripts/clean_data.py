import pandas as pd
import json
from pathlib import Path

# Находит самую свежую по дате папку в raw/openweather_api
def find_latest_raw_folder(base_path: Path) -> Path:
    
    folders = sorted(base_path.rglob("*"))
    valid = [f for f in folders if f.is_dir() and f.name.isdigit() and len(f.name) == 2] # папки дней
    if not valid:
        raise FileNotFoundError('В raw/ не найдено папок с датами!')
    # Берём последнюю папку
    latest_day = valid[-1]
    return latest_day.parent / latest_day.name

# Очистка:
# 1. Температуру - привести к целым числам
def clean_data(raw_folder: Path) -> pd.DataFrame:
    
    records = []
    
    print(f'Ищем файлы в: {raw_folder.absolute()}')
    
    # Читает все JSON из папки RAW, извлекает город и температуру
    for json_file in raw_folder.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        city = data.get("name", "Unknown")
        temp_raw = data.get("main", {}).get("temp")
        
        if temp_raw is not None:
            records.append({
                "city": city,
                "temp_int": round(temp_raw) # округление
            })
        else:
            print(f'Пропуск {city}: поле температуры отсутствует')
        
    df = pd.DataFrame(records)
    
    return df

if __name__ == "__main__":
    # Путь к сырым данным
    raw_folder_path = find_latest_raw_folder(Path("data/raw/openweather_api"))
    
    df_result = clean_data(raw_folder_path)
    
    if not df_result.empty:
        print(f'\nРезультат:\n{df_result}')

    