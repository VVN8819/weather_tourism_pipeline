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

# ВИТРИНА 1: Рейтинг городов + Типы туров + Лучшее время
# Рейтинг городов по комфортности погоды
# рекомендации по типу туров
# Лучшее время для посещения
def create_tourism_rating(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Рейтинг городов + Типы туров + Лучшее время")
    
    # A. Рейтинг городов по комфортности погоды
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
    
    # B. Лучшее время для посещения
    time_map = {
        "Круглогодично": "Круглый год",
        "Май-Сентябрь": "Май — Сентябрь",
        "Май-Октябрь": "Май — Октябрь",
        "Июнь-Август": "Июнь — Август"
    }
    # Форматируем сезон для бизнес-отчёта
    df["best_visit_time"] = df["tourism_season"].map(time_map).fillna(df["tourism_season"])
    
    # Если сейчас подходящий сезон, добавляем пометку
    df.loc[df["tourist_season_match"] == "Да", "best_visit_time"] += "(Сезон открыт)"
    logger.info(f"Лучшее время определено для {len(df)} городов.")
    
    # C. рекомендации по типу туров
    def map_tour_type(row):
        comfort = row["comfort_index"]
        season = row["tourist_season_match"]
        activity = row["recommended_activity"]
        pop = row.get("population", 0)
        
    # Логика подбора типа тура
        if comfort == "Идеально" and season == "Да":
            return "Экскурсионно-пляжный тур"
        elif comfort in ["Идеально", "Комфортно"] and season == "Да":
            if pop > 1_000_000:
                return "Культурно-исторический тур"
            return "Природный и активный отдых"
        elif comfort == "Приемлемо" or season == "Нет":
            if "Музеи" in activity:
                return "СПА и оздоровительный тур"
            return "Городской уикенд / Шоппинг"
        elif comfort == "Некомфортно":
            return "Крытые развлечения и деловой туризм"
        else:
            return "Горящие туры (специальные условия)"
        
    df["recommended_tour_type"] = df.apply(map_tour_type, axis=1)
    logger.info(f"Распределение типов туров: {df['recommended_tour_type'].value_counts().to_dict()}")
    
    # Сортировка и ранжирование
    df_sorted = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    df_sorted["rank"] = range(1, len(df_sorted) + 1)
    
    # Отбираем колонки для итоговой витрины
    report_cols = [
        "rank", "city", "comfort_index", "comfort_score", 
        "tourist_season_match", "final_score", 
        "recommended_activity", "recommended_tour_type", "best_visit_time"  
    ]
    df_report = df_sorted[report_cols].copy()
    
    logger.info(f"Рейтинг сформирован. Лидер: {df_report.iloc[0]['city']} ({df_report.iloc[0]['comfort_index']})")
    return df_report

# Витрина 2: “Сводка по федеральным округам”
# • Средняя температура по округам
# • Количество “комфортных” городов 
# • Общие рекомендации
def create_district_summary(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Сводная по федеральным округам: “комфортный” город + средняя температура + общие рекомендации")
    
    # Создаём временную копию
    df_temp = df.copy()
    # D. город "комфортный", если индекс "Идеально" или "Комфортно"
    df_temp["is_comfortable"] = df_temp["comfort_index"].isin(["Идеально", "Комфортно"])
    
    # E. Средняя температура по округам
    summary = df_temp.groupby("federal_district").agg(
        cities_count=("city", "nunique"),
        comfortable_cities_count=("is_comfortable", "sum"),
        avg_temperature=("temperature", "mean"),
        avg_feels_like=("feels_like", "mean")
    ).reset_index()
    
    # Округление
    for col in ["avg_temperature", "avg_feels_like"]:
        summary[col] = summary[col].round(1)
    
    # счётчик в целое число, NaN, если будет пусто
    summary["comfortable_cities_count"] = summary["comfortable_cities_count"].astype("Int64")
    
    # F. Общие рекомендации
    def generate_recommendation(row):
        temp = row["avg_temperature"]
        comfort_ratio = row["comfortable_cities_count"] / row["cities_count"] if row["cities_count"] > 0 else 0
        
        # Логика рекомендаций
        if temp >= 22 and comfort_ratio >= 0.7:
            return "Идеальные условия для туризма"
        elif temp >= 18 and comfort_ratio >= 0.5:
            return "Комфортная погода в большинстве городов"
        elif temp < 5:
            return "Предлагать СПА/горнолыжные туры"
        elif comfort_ratio < 0.3:
            return "Крытые активности и деловой туризм"
        else:
            return "Мониторить прогноз"
    summary["recommendations"] = summary.apply(generate_recommendation, axis=1)
    logger.info(f'Рекомендации для {len(summary)} округов готовы.')
    
    summary = summary.sort_values("avg_temperature", ascending=False).reset_index(drop=True)
    logger.info(f'Сводная создана для {len(summary)} округов.')
    return summary

# Витрина 3: “Отчет для турагентств”
# • Топ-3 города для поездок сегодня
# • Города, где лучше остаться дома
# • Специальные рекомендации (взять зонт, теплую одежду и т.д.)
def travel_recommendations_report(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    logger.info("Отчет для турагентств: Топ-3 города на сегодня и где лучше остаться дома + Специальные рекомендации")
    
    # G. Топ-3 города для поездок сегодня
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
    df["prior_score"] = df["comfort_score"] + season_bonus
    
    # Сортируем и берём Топ-3
    df_top3 = df.sort_values("prior_score", ascending=False).head(3).copy()
    df_top3["recommendation_priority"] = ["Продавать в первую очередь", "Активно предлагать", "Альтернатива"]
    
    # H. Города, где лучше остаться дома
    bad_weather_keywords = ["гроза", "ливень", "метель", "шторм", "ураган", "туман"]
    
    def is_bad_for_tourism(row):
        comfort = row["comfort_index"]
        season = row["tourist_season_match"]
        weather = str(row["weather_description"]).lower()
        temp = row.get("temperature", 999)
        
        # некомфортно + не сезон
        if comfort == "Некомфортно" and season == "Нет":
            return True
        # Экстремальная температура
        if temp < -10 or temp > 35:
            return True
        # Опасные погодные явления
        if any(keyword in weather for keyword in bad_weather_keywords):
            return True
        # Недостаточно данных для рекомендации
        if comfort == "Недостаточно данных":
            return True
        return False
    
    df_stay_home = df[df.apply(is_bad_for_tourism, axis=1)].copy()
    
    if not df_stay_home.empty:
        df_stay_home["stay_home_reason"] = df_stay_home.apply(
            lambda row: f"{row['comfort_index']}, {row['weather_description']}" if pd.notna(row['weather_description']) else f"{row['comfort_index']}",
            axis=1
        )
        logger.warning(f"Найдено {len(df_stay_home)} городов, где не рекомендуется туризм: {[c for c in df_stay_home['city']]}")
    else:
        logger.info("Все города пригодны для туризма сегодня.")
        df_stay_home["stay_home_reason"] = None
    
    # I. Специальные рекомендации
    # Генерирует список рекомендаций на основе погодных условий
    def get_special_recommendations(row):
        
        recommendations = []
        
        temp = row.get("temperature", 20)
        humidity = row.get("humidity", 50)
        wind = row.get("wind_speed", 0)
        weather = str(row.get("weather_description", "")).lower()
        
        # Осадки
        if any(k in weather for k in ["дождь", "ливень", "гроза", "снег", "метель"]):
            recommendations.append("Взять зонт или дождевик")
        
        # Температура
        if temp < 5:
            recommendations.append("Тёплая одежда и шапка")
        elif temp < 15:
            recommendations.append("Ветровка или лёгкая куртка")
        elif temp > 28:
            recommendations.append("Лёгкая одежда и крем от солнца")
        if temp > 30:
            recommendations.append("Пить больше воды, избегать солнца в пик")
            
        # Ветер
        if wind >= 10:
            recommendations.append("Ветровка, сильный ветер")
        elif wind >= 5:
            recommendations.append("Головной убор может сдуть")
            
        # Влажность
        if humidity >= 80:
            recommendations.append("Дышащая одежда, очень влажно")
        elif humidity <= 30:
            recommendations.append("Увлажняющий крем, низкая влажность")
            
        # Солнце
        if "ясно" in weather or "солнце" in weather:
            recommendations.append("Солнцезащитные очки, головной убор")
        
        # Туман
        if "туман" in weather:
            recommendations.append("Светлая одежда")
        
        # Снег
        if any(k in weather for k in ["снег", "гололёд", "изморозь"]):
            recommendations.append("Не скользящая обувь")
            
        # Если ничего не подошло
        if not recommendations:
            recommendations.append("Погода благоприятная, стандартный гардероб")
        
        return "; ".join(recommendations)
    
    # Применяем ко всем городам
    df_top3["special_recommendations"] = df_top3.apply(get_special_recommendations, axis=1)
    df_stay_home["special_recommendations"] = df_stay_home.apply(get_special_recommendations, axis=1)
    logger.info("Специальные рекомендации готовы для всех городов")
    
    # Объединяем два списка в один отчет с флагом типа рекомендации
    df_top3["report_type"] = "Рекомендовать"
    df_stay_home["report_type"] = "Не рекомендовать"
    
    # Для df_stay_home заполняем пустые колонки
    for col in ["recommendation_priority", "recommended_activity"]:
        if col not in df_stay_home.columns:
            df_stay_home[col] = "—"
    
    # Бизнес-колонки для турагентов
    agency_cols = [
        "report_type",
        "recommendation_priority",  # Приоритет продажи
        "city",
        "temperature",
        "comfort_index",
        "weather_description",
        "recommended_activity",
        "prior_score",
        "special_recommendations"
    ]
    
    sort_col = "prior_score" if "prior_score" in df_top3.columns else "temperature"
    # Объединяем и сортируем: сначала "рекомендовать", потом "не рекомендовать"
    df_report = pd.concat([df_top3[agency_cols], df_stay_home[agency_cols]], ignore_index=True)
    
    df_report = df_report.sort_values(
        ["report_type", sort_col], 
        ascending=[False, False]
    ).reset_index(drop=True)
    
    # Логируем итог
    recommend_count = (df_report["report_type"] == "Рекомендовать").sum()
    avoid_count = (df_report["report_type"] == "Не рекомендовать").sum()
    logger.info(f"Отчет сформирован: {recommend_count} к продаже, {avoid_count} к паузе")
    
    return df_report
    

# Сохранение
def save_aggregated_data(df: pd.DataFrame, output_dir: Path, filename: str, logger: logging.Logger) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    
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
        
        # Создаём рейтинг Витрина 1
        df_rating = create_tourism_rating(df, logger)
        # Сохраняем витрину
        save_aggregated_data(df_rating, aggregated_dir, f"city_tourism_rating.csv", logger)
        logger.info(f'\nИтоговый рейтинг:\n{df_rating.to_string(index=False)}')
        
        # Создаем сводную Витрина 2
        df_districts = create_district_summary(df, logger)
        save_aggregated_data(df_districts, aggregated_dir, f"federal_districts_summary.csv", logger)
        logger.info(f'\nИтоговая сводная:\n{df_districts.to_string(index=False)}')
        
        df_agency = travel_recommendations_report(df, logger)
        save_aggregated_data(df_agency, aggregated_dir, f"travel_recommendations.csv", logger)
        logger.info(f'\nОтчет для турагентств:\n{df_agency.to_string(index=False)}')
        
        logger.info('Витрины успешно созданы')
        
    except FileNotFoundError as e:
        logger.error(f'Файл не найден: {e}')
    except Exception as e:
        logger.error(f'Ошибка выполнения: {e}')