import asyncio
import httpx
import time
import platform
import subprocess
import os
from typing import Dict, List, Any
from loguru import logger

logger.add("logs/deepscan_debug.log", rotation="10 MB", retention="5 days", level="INFO")

class AccessChecker:
    def __init__(self):
        self.white_domains = []
        self.check_domains = []
        self.black_domains = []
        
        self.timeout = httpx.Timeout(7.0)
        # На Android и Linux пинг работает через -c
        self.ping_cmd = "-n" if platform.system().lower() == "windows" else "-c"

    async def _get_latency(self, host: str) -> float:
        """Реальный замер ICMP задержки, безопасный для ЛЮБОЙ ОС"""
        try:
            kwargs = {}
            # Применяем флаги скрытия окна ТОЛЬКО для Windows
            if platform.system().lower() == "windows":
                kwargs['creationflags'] = 0x08000000 

            start_time = time.perf_counter()
            
            # Распаковываем kwargs (на Android он будет пустым, на Windows с флагом)
            process = await asyncio.create_subprocess_exec(
                "ping", self.ping_cmd, "1", host,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs 
            )
            await process.wait()
            
            if process.returncode == 0:
                return round((time.perf_counter() - start_time) * 1000, 1)
            return 0.0
        except Exception as e:
            logger.error(f"Ping error for {host}: {e}")
            return 0.0

    async def run_pure_ping_test(self, domains: list) -> tuple:
        if not domains:
            domains = ["yandex.ru"] 
        
        icmp_tasks = [self._get_latency(domain) for domain in domains]
        icmp_results = await asyncio.gather(*icmp_tasks)
        valid_icmp = [r for r in icmp_results if r > 0]
        avg_icmp_ping = round(sum(valid_icmp) / len(valid_icmp), 1) if valid_icmp else 0.0
        
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            http_tasks = []
            for domain in domains:
                async def get_http_ping(host):
                    try:
                        url = f"https://{host}"
                        start = time.perf_counter()
                        resp = await client.get(url, follow_redirects=True, timeout=self.timeout)
                        latency = (time.perf_counter() - start) * 1000
                        return latency
                    except:
                        return 0.0
                
                http_tasks.append(get_http_ping(domain))
            
            http_results = await asyncio.gather(*http_tasks)
            valid_http = [r for r in http_results if r > 0]
            avg_http_ping = round(sum(valid_http) / len(valid_http), 1) if valid_http else avg_icmp_ping
            
            return (avg_icmp_ping, avg_http_ping)

    async def _check_resource(self, client: httpx.AsyncClient, name: str, host: str, category: str) -> Dict[str, Any]:
        url = f"https://{host}"
        
        logger.info(f"[CHECK] Попытка ICMP Ping для: {name} ({host}) Категория: {category}")
        latency_icmp = await self._get_latency(host)
        icmp_alive = latency_icmp > 0
        
        if icmp_alive:
            logger.debug(f"[PING] {name} ответил по ICMP за {latency_icmp}ms")
        else:
            logger.warning(f"[PING] {name} НЕ ответил по ICMP")

        try:
            logger.info(f"[HTTP] Отправка GET запроса на {url}...")
            start_time = time.perf_counter()
            
            response = await client.get(url, follow_redirects=True, timeout=self.timeout)
            latency_http = (time.perf_counter() - start_time) * 1000
            
            logger.success(f"[OK] {name} доступен. HTTP Latency: {latency_http:.1f}ms, Код: {response.status_code}")
            
            return {
                "name": name, 
                "status": "Доступен", 
                "ping": round(latency_http, 1),
                "icon": "✅",
                "category": category,
                "domain": host
            }
        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            status = "Заблокирован" if icmp_alive else "Недоступен"
            logger.error(f"[BLOCK] {name} - Таймаут! ICMP: {'ЖИВ' if icmp_alive else 'МЕРТВ'}. Итог: {status}")
            icon = "🛡️" if icmp_alive else "🚫"
            return {"name": name, "status": status, "ping": 0, "icon": icon, "category": category, "domain": host}
        except Exception as e:
            err_str = str(e).lower()
            logger.critical(f"[ERROR] Критическая ошибка для {name}: {err_str}")
            if "reset" in err_str or "abort" in err_str:
                return {"name": name, "status": "DPI Reset", "ping": 0, "icon": "⚠️", "category": category, "domain": host}
            return {"name": name, "status": "Ошибка сети", "ping": 0, "icon": "❓", "category": category, "domain": host}
    
    async def run_white_list_test(self) -> List[Dict]:
        test_list = {}
        for domain in self.white_domains:
            name = domain.split('.')[0].upper()
            if domain not in test_list.values():
                test_list[name] = domain
    
        if not test_list:
            test_list["REZERVNY"] = "yandex.ru"

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            tasks = [self._check_resource(client, name, host, "white") for name, host in test_list.items()]
            results = await asyncio.gather(*tasks)
            return {"availability_data": results}

    async def run_check_list_test(self) -> List[Dict]:
        test_list = {}
        for domain in self.check_domains:
            name = domain.split('.')[0].upper()
            if domain not in test_list.values():
                test_list[name] = domain

        if not test_list:
            test_list["REZERVNY"] = "google.com"

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            tasks = [self._check_resource(client, name, host, "check") for name, host in test_list.items()]
            results = await asyncio.gather(*tasks)
            return {"availability_data": results}

    async def run_black_list_test(self) -> List[Dict]:
        test_list = {}
        for domain in self.black_domains:
            name = domain.split('.')[0].upper()
            if domain not in test_list.values():
                test_list[name] = domain

        if not test_list:
            test_list["REZERVNY"] = "youtube.com"

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            tasks = [self._check_resource(client, name, host, "black") for name, host in test_list.items()]
            results = await asyncio.gather(*tasks)
            return {"availability_data": results}