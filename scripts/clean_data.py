import pandas as pd
import json
from pathlib import Path

city_ru_map = {
    "Moscow": "Москва",
    "Saint Petersburg": "Санкт-Петербург",
    "Sochi": "Сочи",
    "Kazan": "Казань",
    "Novosibirsk": "Новосибирск"
}

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
# 2. Названия городов - стандартизировать на русском языке
# 3. Время - привести к единому формату
def clean_data(raw_folder: Path) -> pd.DataFrame:
    
    records = []
    
    # Читает все JSON из папки RAW, извлекает город и температуру
    for json_file in raw_folder.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        main_data = data.get("main", {})
        temp_int = main_data.get("temp")
        feel_temp = main_data.get("feels_like")
        humidity_raw = main_data.get("humidity")
        pressure_raw = main_data.get("pressure")
        
        # Названия городов - стандартизировать на русском языке
        city_en = data.get("name", "Unknown")
        city_ru = city_ru_map.get(city_en, city_en)
        
        if city_ru != city_en:
            print(f'{city_en} -> {city_ru}')
        
        wind_data = data.get("wind", {})
        wind_speed_raw = wind_data.get("speed")
        
        weather_data = data.get("weather", [])
        weather_raw_desc = weather_data[0].get("description", "") if weather_data else ""
        weather_description = weather_raw_desc.strip().lower() if weather_raw_desc else None
        
        # Время - привести к единому формату
        metadata = data.get("_metadata", {})
        col_time_raw = metadata.get("collection_time")
        dt_raw = data.get("dt")
        
        # Если ключа нет
        if col_time_raw is None and "_metadata" in data:
            print(f"В {json_file.name} -> _metadata.keys(): {list(data['_metadata'].keys())}")
        
        # Температуру - привести к целым числам
        if temp_int is not None:
            # Конвертация давления: гПа в мм рт.ст.
            pressure_mmhg = None
            if pressure_raw is not None:
                pressure_mmhg = round(pressure_raw * 0.750062)
                
            wind_speed_ms = None
            if wind_speed_raw is not None:
                wind_speed_ms = round(wind_speed_raw, 1)
            
            records.append({
                "city": city_ru,
                "temperature": round(temp_int), # округление
                "feels_like": round(feel_temp) if feel_temp is not None else None,
                "humidity": humidity_raw,
                "pressure": pressure_mmhg,
                "wind_speed": wind_speed_ms,
                "weather_description": weather_description,
                "date": dt_raw,
                "collection_time": col_time_raw
            })
        else:
            print(f'Пропуск {city_en}: поле температуры отсутствует')
        
    df = pd.DataFrame(records)
    
    # Время - привести к единому формату
    if not df.empty:
        df["collection_time"] = pd.to_datetime(df["collection_time"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], unit="s", errors="coerce")
        df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce").astype("Int64")
        df["pressure"] = pd.to_numeric(df["pressure"], errors="coerce").astype("Int64")
        df["wind_speed"] = pd.to_numeric(df["wind_speed"], errors="coerce").astype("Float64")
        df["weather_description"] = df["weather_description"].astype("string")
        
    return df

if __name__ == "__main__":
    # Путь к сырым данным
    raw_folder_path = find_latest_raw_folder(Path("data/raw/openweather_api"))
    
    df_result = clean_data(raw_folder_path)
    
    if not df_result.empty:
        print(f'\nРезультат:\n{df_result}')
    else:
        print("\nDataFrame пустой. Проверьте наличие .json файлов в указанной папке.")

    