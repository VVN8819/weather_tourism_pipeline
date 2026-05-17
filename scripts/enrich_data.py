import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

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

city_population = {
    "Москва": 13100000,
    "Санкт-Петербург": 5600000,
    "Сочи": 450000,
    "Казань": 1300000,
    "Новосибирск": 1630000
}

tourism_season_dict = {
    "Москва": "Круглогодично",
    "Санкт-Петербург": "Май-Сентябрь",
    "Сочи": "Май-Октябрь",
    "Казань": "Май-Сентябрь",
    "Новосибирск": "Июнь-Август"
}

# ============== Логирование  ===================
def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"enrich_log.txt"
    
    logger = logging.getLogger("enrich_pipeline")
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

# Находит самый свежий по дате файл в data/cleaned/
def find_latest_cleaned_csv(base_path: Path) -> Path:
    files = list(base_path.glob("weather_cleaned_*.csv"))
    if not files:
        raise FileNotFoundError('В data/cleaned/ не найдено файлов weather_cleaned_*.csv')
    # Берём файл с самым поздним временем изменения
    return max(files, key=lambda p: p.stat().st_mtime)

# обогащение данных о погоде
def enrich_table(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Обогащение данных встроенными справочниками")
    
    # применение справочников к колонке city
    df["federal_district"] = df["city"].map(city_federal_district)
    df["timezone"] = df["city"].map(city_timezone)
    df["population"] = df["city"].map(city_population)
    df["tourism_season"] = df["city"].map(tourism_season_dict)
    
    df["population"] = pd.to_numeric(df["population"], errors="coerce").astype("Int64")
    
    # города не в списке
    missing_cities = df[df["federal_district"].isna()]["city"].drop_duplicates().tolist()
    if missing_cities:
        logger.warning(f'Не найдены в справочнике: {missing_cities}')
    else:
        logger.info('Все города успешно обогащены.')
     
    return df

# Расчёт шкалы комфорта для туризма
def enrich_comfort_index(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Расчёт индекса комфортности погоды для туризма.")
    
    t = df["temperature"]
    h = df["humidity"]
    w = df["wind_speed"]
    
    # Проверка на наличие данных
    valid = t.notna() & h.notna() & w.notna()
    
    ideal = (t.between(18, 26)) & (h.between(40, 70)) & (w < 5)
    comfort = (t.between(15, 30)) & (h.between(30, 80)) & (w < 8)
    accept = (t.between(5, 35)) & (w < 12)
    
    df['comfort_index'] = np.select(
        [valid & ideal, valid & comfort, valid & accept],
        ["Идеально", "Комфортно", "Приемлемо"],
        default="Некомфортно"
    )
    df.loc[~valid, 'comfort_index'] = "Недостаточно данных"
    
    # Лог
    dist = df['comfort_index'].value_counts().to_dict()
    logger.info(f'Распределение по уровням: {dist}')
    return df

# Рекомендуемый тип активности
def enrich_recommended_activity(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Расчёт рекомендуемого типа активности.")
    
    # на основе уровня комфорта
    activity_map = {
        "Идеально": "Прогулки и экскурсии",
        "Комфортно": "Прогулки и экскурсии",
        "Приемлемо": "Музеи и крытые активности",
        "Некомфортно": "Домашний отдых",
        "Недостаточно данных": "Уточните прогноз"
    }
    
    df["recommended_activity"] = df["comfort_index"].map(activity_map)
    
    # если в описании есть дождь/гроза, переводим в "Музеи"
    rain_keywords = ["дождь", "гроза", "ливень", "снег", "метель"]
    is_rainy = df["weather_description"].str.contains("|".join(rain_keywords), na=False)
    df.loc[is_rainy & (df["comfort_index"] != "Некомфортно"), "recommended_activity"] = "Музеи и крытые активности"
    
    logger.info(f'Распределение активностей: {df["recommended_activity"].value_counts().to_dict()}')
    return df

# Сохранение
def save_enriched_data(df: pd.DataFrame, output_dir: Path, logger: logging.Logger) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = output_dir / f"weather_enriched_{date_str}.csv"
    
    df.to_csv(filepath, index=False, encoding="utf-8")
    logger.info(f'Сохранено: {filepath}')
    return filepath

if __name__ == "__main__":
    logger = setup_logger(Path("data/enriched"))
    logger.info('Запуск слоя ENRICHED')
    
    cleaned_dir = Path("data/cleaned")
    enriched_dir = Path("data/enriched")
    try:
        # Находим последний очищенный файл
        latest_csv = find_latest_cleaned_csv(cleaned_dir)
        logger.info(f'Загрузка: {latest_csv.name}')

        # Читаем последний очищенный файл
        df = pd.read_csv(latest_csv)
        logger.info(f'Загружено строк: {len(df)}')
        
        # Применяем enrich
        df = enrich_table(df, logger)
        df = enrich_comfort_index(df, logger)
        df = enrich_recommended_activity(df, logger)
        
        
        # Сохраняем обновления
        save_enriched_data(df, enriched_dir, logger)
        logger.info(f'Добавление завершено')
        
        logger.info(f'\nРезультат:\n{df}')
    except Exception as e:
        logger.error(f'Ошибка выполнения: {e}')