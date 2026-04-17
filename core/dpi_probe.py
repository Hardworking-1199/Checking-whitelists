import random
from loguru import logger
import ctypes
import os

# Безопасный импорт Scapy (спасает от краша на Android)
try:
    from scapy.all import IP, TCP, ICMP, sr1, conf
    conf.verb = 0
    SCAPY_AVAILABLE = True
except Exception as e:
    logger.warning(f"Модуль DPI отключен (Нормально для Android/отсутствия root): {e}")
    SCAPY_AVAILABLE = False

class DPIProbe:
    def __init__(self):
        self.global_white_list = [
            "google.com", "microsoft.com", "amazon.com", "twitch.tv", 
            "github.com", "cloudflare.com", "steampowered.com", 
            "epicgames.com", "spotify.com", "netflix.com", 
            "reddit.com", "wikipedia.org", "adobe.com", "zoom.us"
        ]
        self.common_mtu_values = [1400, 1380, 1350, 1280, 576]

    def _is_admin(self):
        """Проверка прав. Если Scapy не загрузился - всегда False."""
        if not SCAPY_AVAILABLE:
            return False
        try:
            return os.getuid() == 0 if os.name != 'nt' else ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def test_mtu_path(self, target: str = "1.1.1.1") -> dict:
        if not self._is_admin():
            logger.error("DPI Engine отключен: Нет прав или неподдерживаемая ОС (Android)")
            return {"error": "No Admin Rights / Mobile OS"}

        logger.info(f"Запуск MTU Discovery (Цель: {target})...")
        results = {}
        
        for size in self.common_mtu_values:
            payload_size = size - 28
            packet = IP(dst=target, flags="DF") / ICMP() / ("X" * payload_size)
            
            try:
                reply = sr1(packet, timeout=1.5, verbose=0)
                if reply is None:
                    results[size] = "Dropped"
                elif reply.haslayer(ICMP) and reply.getlayer(ICMP).type == 3:
                    results[size] = "Frag Needed"
                else:
                    results[size] = "Success"
                    if size == 1400: break
            except Exception as e:
                results[size] = f"Error: {e}"

        return results

    def check_white_list_tampering(self) -> dict:
        if not self._is_admin():
            return {"error": "No Admin Rights / Mobile OS"}

        test_targets = random.sample(self.global_white_list, 3)
        report = {}

        for domain in test_targets:
            logger.info(f"DPI Handshake тест: {domain}...")
            try:
                syn_packet = IP(dst=domain) / TCP(dport=443, flags="S")
                response = sr1(syn_packet, timeout=2, verbose=0)
                
                if response and response.haslayer(TCP):
                    flags = response.getlayer(TCP).flags
                    if flags == 0x12:
                        report[domain] = "Clean"
                    elif flags == 0x14:
                        report[domain] = "Tampered (DPI RST)"
                        logger.warning(f"ВНИМАНИЕ: Обнаружен DPI-сброс для {domain}")
                    else:
                        report[domain] = f"Flags: {hex(flags)}"
                else:
                    report[domain] = "No Response (Silent Drop)"
            except Exception as e:
                logger.warning(f"DPI тест для {domain} не удался: {e}")
                report[domain] = "Error: Network Unavailable"

        return report

    async def run_dpi_test(self):
        import asyncio
        loop = asyncio.get_running_loop()
        
        logger.info("Запуск комплексного DPI тестирования...")
        
        mtu_results = await loop.run_in_executor(None, self.test_mtu_path)
        tamper_results = await loop.run_in_executor(None, self.check_white_list_tampering)
       
        return {
            "mtu": mtu_results,
            "tampering": tamper_results,
            "status": "Complete" if SCAPY_AVAILABLE else "Skipped (Mobile/No Root)"
        }