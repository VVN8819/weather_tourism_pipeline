import logging
from pathlib import Path
import pandas as pd

# ============== Логирование  ===================
def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"aggregation_log.txt"
    
    logger = logging.getLogger("aggregation_pipeline")
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

# Находит самый свежий по дате файл в data/enriched/
def find_latest_enriched_csv(base_path: Path) -> Path:
    files = list(base_path.glob("weather_enriched_*.csv"))
    if not files:
        raise FileNotFoundError('В data/enriched/ не найдено файлов weather_enriched_*.csv')
    # Берём файл с самым поздним временем изменения
    return max(files, key=lambda p: p.stat().st_mtime)

# Рейтинг городов по комфортности погоды
def create_tourism_rating(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Рейтинг городов по комфортности погоды")
    
    # 1 строка на город (на случай повторных запусков)
    df = df.drop_duplicates(subset=["city"], keep="last").copy()
    
    # справочник баллов
    score_map = {
        "Идеально": 100,
        "Комфортно": 80,
        "Приемлемо": 50,
        "Некомфортно": 20,
        "Недостаточно данных": 0
    }
    df["comfort_score"] = df["comfort_index"].map(score_map)
    
    # Бонус за совпадение с туристическим сезоном
    season_bonus = df["tourist_season_match"].map({"Да": 10, "Нет": 0})
    df["final_score"] = df["comfort_score"] + season_bonus
    
    # Сортировка и ранжирование
    df_sorted = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    df_sorted["rank"] = range(1, len(df_sorted) + 1)
    
    # Отбираем колонки для итоговой витрины
    report_cols = [
        "rank", "city", "comfort_index", "comfort_score", 
        "tourist_season_match", "final_score", "recommended_activity"
    ]
    df_report = df_sorted[report_cols].copy()
    
    logger.info(f"Рейтинг сформирован. Лидер: {df_report.iloc[0]['city']} ({df_report.iloc[0]['comfort_index']})")
    return df_report

# Сохранение
def save_aggregated_data(df: pd.DataFrame, output_dir: Path, logger: logging.Logger) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"city_tourism_rating.csv"
    
    df.to_csv(filepath, index=False, encoding="utf-8")
    logger.info(f'Сохранено: {filepath}')
    return filepath

if __name__ == "__main__":
    logger = setup_logger(Path("data/aggregated"))
    logger.info('Запуск слоя AGGREGATED')
    
    enriched_dir = Path("data/enriched")
    aggregated_dir = Path("data/aggregated")
    try:        
        # Находим последний enriched файл
        latest_csv = find_latest_enriched_csv(enriched_dir)
        logger.info(f'Загрузка: {latest_csv.name}')

        # Читаем последний enriched файл
        df = pd.read_csv(latest_csv)
        logger.info(f'Загружено строк: {len(df)}')
        
        # Создаём рейтинг
        df_rating = create_tourism_rating(df, logger)
        
        # Сохраняем витрину
        save_aggregated_data(df_rating, aggregated_dir, logger)
        
        logger.info(f'\nИтоговый рейтинг:\n{df_rating.to_string(index=False)}')
        logger.info('Витрина "Рейтинг городов для туризма" успешно создана')
        
    except FileNotFoundError as e:
        logger.error(f'Файл не найден: {e}')
    except Exception as e:
        logger.error(f'Ошибка выполнения: {e}')