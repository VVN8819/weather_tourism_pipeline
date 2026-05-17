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

if __name__ == "__main__":
    logger = setup_logger(Path("data/aggregated"))
    logger.info('Запуск слоя AGGREGATED')
    
    enriched_dir = Path("data/enriched")
    try:        
        # Находим последний enriched файл
        latest_csv = find_latest_enriched_csv(enriched_dir)
        logger.info(f'Загрузка: {latest_csv.name}')

        # Читаем последний enriched файл
        df = pd.read_csv(latest_csv)
        logger.info(f'Загружено строк: {len(df)}')
        
    except Exception as e:
        logger.error(f'Ошибка выполнения: {e}')