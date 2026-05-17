import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import logging

city_ru_map = {
    "Moscow": "Москва",
    "Saint Petersburg": "Санкт-Петербург",
    "Sochi": "Сочи",
    "Kazan": "Казань",
    "Novosibirsk": "Новосибирск"
}

# ============== Логирование  ===================
def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"cleaning_log_{date_str}.txt"
    
    logger = logging.getLogger("clean_pipeline")
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
        log_file,
        mode="w",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Лог в консоль (для удобства отладки)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

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
# 4. Валидация - проверить разумность данных (температура от -50 до +60°C)
def clean_data(raw_folder: Path, logger: logging.Logger) -> pd.DataFrame:
    
    # применённые правила
    rules = [
        "1. Округление температуры до целых",
        "2. Перевод названий городов на русский (словарь)",
        "3. Парсинг времени в формат datetime",
        "4. Валидация температуры: диапазон [-50; +60]°C",
        "5. Конвертация давления: гПа в мм рт.ст.",
        "6. Округление скорости ветра до 0.1 м/с",
        "7. Приведение описания погоды к нижнему регистру"        
    ]
    logger.info('Применённые правила очистки:')
    for rule in rules:
        logger.info(f'{rule}')
    
    # список для df
    records = []
    
    # считаем возникшие проблемы для logger
    problems_count = 0
    
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
            logger.warning(f"В {json_file.name} -> _metadata.keys() нет: {list(data['_metadata'].keys())}")
            problems_count += 1
        
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
            logger.warning(f'Пропуск {city_en}: поле температуры отсутствует')
            problems_count += 1
            continue
    
    initial_count = len(records)
    logger.info(f'Количество исходных записей: {initial_count}')
    
    df = pd.DataFrame(records)
    
    # Валидация - проверить разумность данных (температура от -50 до +60°C)
    if not df.empty and "temperature" in df.columns:
        # True, если температура в диапазоне [-50, 60]
        valid_temp_mask = (df["temperature"] >= -50) & (df["temperature"] <= 60)
        invalid_count = (~valid_temp_mask).sum()
        
        if invalid_count > 0:
            logger.warning(f'Валидация: исключено {invalid_count} строк с температурой вне диапазона [-50°C; +60°C]')
            
        # Оставляем только валидные строки + сбрасываем индекс
        df = df[valid_temp_mask].copy().reset_index(drop=True)
    
    final_count = len(df)
    logger.info(f'Количество очищенных записей: {final_count}')
    logger.info(f'Количество найденных проблем: {problems_count}')
    
    # Время - привести к единому формату
    if not df.empty:
        df["collection_time"] = pd.to_datetime(df["collection_time"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], unit="s", errors="coerce")
        df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce").astype("Int64")
        df["pressure"] = pd.to_numeric(df["pressure"], errors="coerce").astype("Int64")
        df["wind_speed"] = pd.to_numeric(df["wind_speed"], errors="coerce").astype("Float64")
        df["weather_description"] = df["weather_description"].astype("string")
        
    return df

# Сохранение в CSV
def save_cleaned_data(df: pd.DataFrame, output_dir: Path, logger: logging.Logger) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"weather_cleaned_{date_str}.csv"
    filepath = output_dir / filename
    
    df.to_csv(filepath, index=False, encoding="utf-8")
    logger.info(f'Очищенные данные сохранены: {filepath}')
    return filepath

if __name__ == "__main__":
    # Сохранение логов
    clean_dir = Path("data/cleaned")
    logger = setup_logger(clean_dir)
    logger.info('Запуск слоя CLEANED')
    
    # Путь к сырым данным
    raw_folder_path = find_latest_raw_folder(Path("data/raw/openweather_api"))
    
    df_result = clean_data(raw_folder_path, logger)
    
    if not df_result.empty:
        output_dir = Path("data/cleaned")
        saved_path = save_cleaned_data(df_result, output_dir, logger)
        logger.info(f'\nРезультат:\n{df_result}')

    else:
        logger.error('\nDataFrame пустой. Проверьте наличие .json файлов в указанной папке.')

    