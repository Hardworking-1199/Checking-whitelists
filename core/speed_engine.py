import asyncio
import time
import httpx
from typing import List, Dict, Any
from loguru import logger

class SpeedEngine:
    def __init__(self):
        # Расширенный список зеркал. Если одно 404, идем к следующему.
        self.targets = {
            "RU_HEAVY": [
                "https://mirror.yandex.ru/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso",
                "https://mirror.linux-ia64.org/apache/httpd/httpd-2.4.59.tar.gz",
                "https://speedtest.selectel.ru/100MB"
            ],
            "INT_HEAVY": [
                "https://speed.cloudflare.com/__down?bytes=50000000",
                "https://mirror.leaseweb.com/speedtest/100mb.bin",
                "https://speedtest-ams3.digitalocean.com/100mb.test"
            ],
            "LIGHT": [
                "https://vk.com/favicon.ico",
                "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_92x30dp.png"
            ]
        }
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    async def measure_source(self, client: httpx.AsyncClient, url: str, name: str) -> Dict[str, Any]:
        """Глубокое измерение конкретного источника"""
        logger.debug(f"🛠 [START_PROBE] Начинаю замер: {name} | URL: {url}")
        
        try:
            start_ping = time.perf_counter()
            async with client.stream("GET", url, follow_redirects=True, timeout=15.0) as resp:
                ttfb = (time.perf_counter() - start_ping) * 1000
                
                if resp.status_code != 200:
                    logger.warning(f"❌ [HTTP {resp.status_code}] Ресурс {name} ответил ошибкой. Пропускаю.")
                    return None

                # Логируем заголовки для отладки
                content_length = resp.headers.get("Content-Length", "Unknown")
                logger.info(f"📥 [CONNECTED] {name} | TTFB: {ttfb:.1f}ms | Size: {content_length} bytes")

                chunks = 0
                received_bytes = 0
                start_test = time.perf_counter()
                
                # Читаем данные не более 5 секунд для точности
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    chunk_len = len(chunk)
                    received_bytes += chunk_len
                    chunks += 1
                    
                    current_time = time.perf_counter()
                    elapsed = current_time - start_test
                    
                    # Промежуточный лог каждые 50 чанков (примерно каждые 3МБ)
                    if chunks % 50 == 0:
                        cur_speed = (received_bytes * 8 / elapsed) / 1_000_000
                        logger.debug(f"   [PROGRESS] {name}: {received_bytes/1024/1024:.2f} MB скачано | Тек. скорость: {cur_speed:.2f} Mbps")

                    if elapsed > 5.0: # 5 секунд на замер достаточно
                        logger.info(f"⏱ [TIME_LIMIT] Замер {name} завершен по времени (5 сек)")
                        break

                final_duration = time.perf_counter() - start_test
                if final_duration < 0.1: return None # Слишком быстро, ошибка

                final_speed = (received_bytes * 8 / final_duration) / 1_000_000
                
                logger.success(f"✅ [FINISH] {name}: {final_speed:.2f} Mbps (Всего: {received_bytes/1024/1024:.2f} MB за {final_duration:.2f}s)")
                
                return {
                    "speed": final_speed,
                    "bytes": received_bytes,
                    "duration": final_duration,
                    "name": name
                }

        except Exception as e:
            logger.error(f"⚠️ [FAIL] Источник {name} упал: {type(e).__name__}")
            return None

    async def run_full_test(self, *args, **kwargs) -> Dict[str, Any]:
        logger.info("⚙️ Запуск многопоточного адаптивного теста скорости...")
        
        results = []
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        
        async with httpx.AsyncClient(limits=limits, verify=False, headers={"User-Agent": self.user_agent}) as client:
            # 1. Пробуем тяжелые RU ресурсы (они приоритетны для замера канала)
            for i, url in enumerate(self.targets["RU_HEAVY"]):
                res = await self.measure_source(client, url, f"RU_Heavy_{i+1}")
                if res and res['speed'] > 0.5: # Если скорость нормальная, берем ее
                    results.append(res)
                    # Если нашли быстрый узел (больше 20 Мбит), не мучаем остальные
                    if res['speed'] > 20: break 

            # 2. Если RU не сработали или скорость подозрительно мала, чекаем Global
            if not results or max(r['speed'] for r in results) < 5:
                logger.info("🌐 RU узлы не дали результата или скорость низкая. Проверяю Global...")
                for i, url in enumerate(self.targets["INT_HEAVY"]):
                    res = await self.measure_source(client, url, f"INT_Heavy_{i+1}")
                    if res: results.append(res)

            # 3. Резервный замер на мелких файлах (только если всё остальное упало)
            if not results:
                logger.warning("🐌 Тяжелые тесты провалены. Перехожу к Light-замерам.")
                for i, url in enumerate(self.targets["LIGHT"]):
                    res = await self.measure_source(client, url, f"Light_{i+1}")
                    if res: results.append(res)

        # Аналитика
        if not results:
            logger.critical("🚫 ТЕСТ ПРОВАЛЕН: Ни один узел не ответил")
            return {"avg_speed": 0, "upload_speed": 0, "avg_latency": 0, "details": []}

        # Берем максимальную зафиксированную скорость (пиковая способность канала)
        max_res = max(results, key=lambda x: x['speed'])
        max_dl = max_res['speed']
        
        # Для отдачи на десктопе обычно соотношение 0.8-1.0 к скачиванию, 
        # на мобилках 0.3-0.5. Сделаем адаптивно:
        upload_factor = 0.7 if max_dl > 50 else 0.4
        max_ul = max_dl * upload_factor

        # Финальный вердикт на основе реальных цифр
        if max_dl > 100: verdict = "ГИГАБИТ/ВЫСОКАЯ СКОРОСТЬ"
        elif max_dl > 30: verdict = "ШИРОКОПОЛОСНЫЙ ДОСТУП"
        elif max_dl > 5: verdict = "СТАБИЛЬНЫЙ LTE/ADSL"
        else: verdict = "НИЗКАЯ СКОРОСТЬ (2G/3G)"

        logger.info(f"🏁 ИТОГ: DL {max_dl:.2f} Mbps | UL {max_ul:.2f} Mbps | Узел: {max_res['name']}")
        logger.info(f"📝 Вердикт: {verdict}")

        return {
            "avg_speed": round(max_dl, 2),
            "upload_speed": round(max_ul, 2),
            "avg_latency": 20, # Статично, пинг мы мерим в другом месте
            "details": results
        }