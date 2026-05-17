import logging
from pathlib import Path
from datetime import datetime
import pandas as pd

# Справочник: Федеральный округ
city_federal_district = {
    "Москва": "Центральный ФО",
    "Санкт-Петербург": "Северо-Западный ФО",
    "Сочи": "Южный ФО",
    "Казань": "Приволжский ФО",
    "Новосибирск": "Сибирский ФО"
}

# ============== Логирование  ===================
def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"enrich_log_{date_str}.txt"
    
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

def enrich_table(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Добавление колонки 'federal_district'")
    
    # добавить к данным о погоде Федеральный округ
    df["federal_district"] = df["city"].map(city_federal_district)
    # города не в списке
    missing_cities = df[df["federal_district"].isna()]["city"].drop_duplicates().tolist()
    if missing_cities:
        logger.warning(f'Не найдены в справочнике Федеральный округ: {missing_cities}')
    else:
        logger.info('Все города успешно сопоставлены с федеральными округами.')
        
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
    enriched_der = Path("data/enriched")
    try:
        # Находим последний очищенный файл
        latest_csv = find_latest_cleaned_csv(cleaned_dir)
        logger.info(f'Загрузка: {latest_csv.name}')

        # Читаем последний очищенный файл
        df = pd.read_csv(latest_csv)
        logger.info(f'Загружено строк: {len(df)}')
        
        # Применяем enrich_table
        df = enrich_table(df, logger)
        print(df)
        
        # Сохраняем обновления
        save_enriched_data(df, enriched_der, logger)
        logger.info(f'Добавление завершено')
    except Exception as e:
        logger.error(f'Ошибка выполнения: {e}')