from typing import Dict, Any, List
from loguru import logger

class ReportGenerator:
    def __init__(self):
        self.zones = {
            "CRITICAL": "СЕТЬ НЕДОСТУПНА / ФАТАЛЬНЫЙ СБОЙ",
            "WHITE_ZONE": "РЕЖИМ БЕЛЫХ СПИСКОВ (Блокировка внешнего сегмента)",
            "PARTIAL": "ЗОНА ЧАСТИЧНОЙ ФИЛЬТРАЦИИ (Обнаружен DPI)",
            "OPEN": "СВОБОДНЫЙ ДОСТУП (Фильтры не обнаружены)"
        }

    def calculate_connection_quality_score(self, dl: float, ul: float, ping: float, dpi_results: dict = None) -> tuple:
        """Рассчитывает качество связи по формуле: ПРИОРИТЕТЫ: Ping(50%) + Speed DL(30%) + Speed UL(20%) + MTU"""
        score = 0
        
        # === 1. PING (50 баллов) ===
        ping_score = 0
        if ping == 0:
            ping_score = 0
        elif ping < 70:
            ping_score = 50
        elif ping < 150:
            ping_score = 35
        elif ping < 300:
            ping_score = 20
        else:
            ping_score = 5
        
        # === 2. DOWNLOAD (30 баллов) ===
        dl_score = 0
        if dl == 0:
            dl_score = 0
        elif dl > 50:
            dl_score = 30
        elif dl > 20:
            dl_score = 20
        elif dl > 5:
            dl_score = 10
        else:
            dl_score = 5
        
        # === 3. UPLOAD (20 баллов) ===
        ul_score = 0
        if ul == 0:
            ul_score = 0
        elif ul > 10:
            ul_score = 20
        elif ul > 5:
            ul_score = 15
        elif ul > 1:
            ul_score = 5
        else:
            ul_score = 0
        
        # === 4. MTU бонус (опционально) ===
        mtu_bonus = 0
        if dpi_results and isinstance(dpi_results, dict):
            mtu_data = dpi_results.get('mtu', {})
            if mtu_data and isinstance(mtu_data, dict):
                if mtu_data.get(1400) == 'Success':
                    pass
                elif mtu_data.get(1350) == 'Success':
                    mtu_bonus = 5
                elif mtu_data.get(1280) == 'Success':
                    mtu_bonus = 10
                elif mtu_data.get(576) == 'Success':
                    mtu_bonus = 20
        
        score = ping_score + dl_score + ul_score + mtu_bonus
        
        if score >= 90:
            desc = "Отличное"
        elif score >= 70:
            desc = "Хорошее"
        elif score >= 50:
            desc = "Нормальное"
        elif score >= 30:
            desc = "Плохое"
        else:
            desc = "Критическое"
        
        return (score, desc)

    def analyze(self, white_data: Dict, check_data: Dict, black_data: Dict, dpi_data: dict = None) -> Dict[str, Any]:
        logger.info("Глубокий анализ данных...")

        availability_data = []
        
                # === СБОР ДАННЫХ (ИСПРАВЛЕННЫЙ ПОРЯДОК И ОТЛАДКА) ===
        logger.info(f"[REPORT_GEN DEBUG] white_data type: {type(white_data)}, keys: {white_data.keys() if isinstance(white_data, dict) else 'N/A'}")
        logger.info(f"[REPORT_GEN DEBUG] check_data type: {type(check_data)}, keys: {check_data.keys() if isinstance(check_data, dict) else 'N/A'}")
        logger.info(f"[REPORT_GEN DEBUG] black_data type: {type(black_data)}, keys: {black_data.keys() if isinstance(black_data, dict) else 'N/A'}")
        
        # Сначала белый список (важно для приоритета)
        if isinstance(white_data, dict) and 'availability_data' in white_data:
            count = len(white_data['availability_data'])
            logger.info(f"[REPORT_GEN DEBUG] Добавлено {count} элементов из белого списка")
            availability_data.extend(white_data['availability_data'])
        else:
            logger.error("[REPORT_GEN DEBUG] white_data пустой или нет ключа 'availability_data'!")
        
        # Потом проверочный список
        if isinstance(check_data, dict) and 'availability_data' in check_data:
            count = len(check_data['availability_data'])
            logger.info(f"[REPORT_GEN DEBUG] Добавлено {count} элементов из списка проверки")
            availability_data.extend(check_data['availability_data'])
        else:
            logger.error("[REPORT_GEN DEBUG] check_data пустой или нет ключа 'availability_data'!")
        
        # Потом черный список
        if isinstance(black_data, dict) and 'availability_data' in black_data:
            count = len(black_data['availability_data'])
            logger.info(f"[REPORT_GEN DEBUG] Добавлено {count} элементов из черного списка")
            availability_data.extend(black_data['availability_data'])
        else:
            logger.error("[REPORT_GEN DEBUG] black_data пустой или нет ключа 'availability_data'!")
        
        logger.info(f"[REPORT_GEN DEBUG] ИТОГО в availability_data: {len(availability_data)} элементов")

                # === ОТЛАДКА: ПРОВЕРКА КАТЕГОРИЙ ===
        logger.info(f"[REPORT_GEN DEBUG] Всего элементов в availability_data: {len(availability_data)}")
        categories_found = {}
        for item in availability_data:
            cat = item.get('category', 'NO_CATEGORY_KEY')
            categories_found[cat] = categories_found.get(cat, 0) + 1
        
        logger.info(f"[REPORT_GEN DEBUG] Найденные категории: {categories_found}")
        
        # Если белый список пуст, покажем пример первого элемента
        if not any(item.get('category') == 'white' for item in availability_data):
            logger.warning("[REPORT_GEN DEBUG] Категория 'white' НЕ НАЙДЕНА! Примеры элементов:")
            for item in availability_data[:3]:
                logger.warning(f"[REPORT_GEN DEBUG] {item}")
        # ============================================

        # Считаем количество доменов в каждой категории
        white_total = len([i for i in availability_data if i.get('category') == 'white'])
        check_total = len([i for i in availability_data if i.get('category') == 'check'])
        
        # Считаем количество доступных доменов
        white_accessible = sum(1 for i in availability_data 
                               if i.get('category') == 'white' and i.get('status').lower() == 'доступен')
        check_accessible = sum(1 for i in availability_data 
                               if i.get('category') == 'check' and i.get('status').lower() == 'доступен')
        
                # Вычисляем проценты (от 0.0 до 1.0)
        w_rate = (white_accessible / white_total) if white_total > 0 else 0.0
        c_rate = (check_accessible / check_total) if check_total > 0 else 0.0
        
        # === ОТЛАДКА ВНУТРИ ГЕНЕРАТОРА ===
        logger.info(f"[REPORT_GEN] White: {white_accessible}/{white_total} -> {w_rate:.3f}")
        logger.info(f"[REPORT_GEN] Check: {check_accessible}/{check_total} -> {c_rate:.3f}")
        
        # Если белый список пуст или равен нулю, покажем предупреждение
        if white_total == 0:
            logger.error("[REPORT_GEN] ERROR: white_total is 0! Cannot calculate rate.")
        
        # === ЛОГИЧЕСКАЯ МАТРИЦА СОСТОЯНИЙ ===
        
        # 1. НЕТ ИНТЕРНЕТА: Если вообще ничего не доступно
        if w_rate == 0 and c_rate == 0:
            current_zone = self.zones["CRITICAL"]
            
        # 2. ЗОНА БЕЛЫХ СПИСКОВ: Белые работают (>0%), но проверочные почти недоступны (<10%)
        elif w_rate > 0 and c_rate < 0.1:
            current_zone = self.zones["WHITE_ZONE"]
            
        # 3. СВОБОДНЫЙ ИНТЕРНЕТ: Проверочные доступны более чем на 70%
        elif c_rate >= 0.7:
            current_zone = self.zones["OPEN"]
            
        # 4. ЧАСТИЧНЫЕ ОГРАНИЧЕНИЯ: Все остальные случаи (есть доступ к белым, но проверочных < 70%)
        else:
            current_zone = self.zones["PARTIAL"]

        # === МЕТРИКИ (ПИНГ И СКОРОСТЬ) ===
        http_ping = 0.0
        icmp_ping = white_data.get('avg_latency', 0.0)
        
        if isinstance(white_data, dict) and 'availability_data' in white_data:
            pings = [item.get('ping', 0) for item in white_data['availability_data'] 
                     if item.get('status').lower() == 'доступен' and item.get('ping', 0) > 0]
            http_ping = sum(pings) / len(pings) if pings else icmp_ping
        else:
            http_ping = icmp_ping

        dl = white_data.get('avg_speed', 0.0)
        ul = white_data.get('upload_speed', 0.0)
        
        quality_score, quality_text = self.calculate_connection_quality_score(dl, ul, http_ping, dpi_data)

        return {
            "zone_status": current_zone,
            "connection_quality": quality_text,
            "quality_score": quality_score,
            "availability_data": availability_data,
            "statistics": {
                "white_rate": round(w_rate, 2),
                "check_rate": round(c_rate, 2),
                "white_accessible_count": white_accessible,
                "white_total_count": white_total,
                "check_accessible_count": check_accessible,
                "check_total_count": check_total,
            },
            "dpi_report": dpi_data,
            "metrics": {
                "ping_http": http_ping,
                "ping_icmp": icmp_ping,
                "dl": f"{dl:.2f}",
                "ul": f"{ul:.2f}"
            }
        }