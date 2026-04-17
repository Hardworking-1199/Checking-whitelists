import asyncio
import json
import re
import os
import flet as ft
from loguru import logger

os.environ["FLET_RENDER_VIA_SKIA"] = "1"
try:
    if os.name == 'nt':
        import ctypes
        # Скрываем окно консоли, если оно было открыто
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
except Exception:
    pass
# ============================================================

class FletLogHandler:
    def __init__(self, log_list, page):
        self.log_list = log_list
        self.page = page
        self.hover_scale_factor = 1.05

    def write(self, message):
        msg_text = message.strip()
        
        # Определяем цвет по ключевым словам (используем regex для точности)
        color = ft.colors.GREY_400 # Цвет по умолчанию
        
        if re.search(r'\|\s*CRITICAL\s*\|', msg_text) or re.search(r'\|\s*ERROR\s*\|', msg_text):
            color = ft.colors.RED_ACCENT
        elif re.search(r'\|\s*WARNING\s*\|', msg_text):
            color = ft.colors.ORANGE_ACCENT
        elif re.search(r'\|\s*SUCCESS\s*\|', msg_text) or re.search(r'\[OK\]', msg_text):
            color = ft.colors.GREEN_ACCENT
        elif re.search(r'\|\s*INFO\s*\|', msg_text):
            color = ft.colors.BLUE_ACCENT
        elif re.search(r'\|\s*DEBUG\s*\|', msg_text):
            color = ft.colors.CYAN # Добавим отдельный цвет для DEBUG
            
        self.log_list.controls.append(
            ft.Text(msg_text, size=12, font_family="Consolas", color=color)
        )
        
        if len(self.log_list.controls) > 100:
            self.log_list.controls.pop(0)
        self.page.update()

class NetProfileApp:
    def __init__(self, page: ft.Page):
        self.page = page
        
        self.speed_engine = None
        self.dpi_probe = None
        self.access_checker = None
        self.report_gen = None
        self.last_report = None
        self.hover_scale_factor = 1.05
        
        self.load_settings()
        self.setup_page()
        self.setup_ui_components()
        
        handler = FletLogHandler(self.log_list, self.page)
        logger.add(handler.write, format="{time:HH:mm:ss} | {message}")
       
    def get_settings_path(self):
        return os.path.join(os.path.dirname(__file__), "settings.json")

    def load_settings(self):
        path = self.get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.white_domains = data.get("white", [])
                    self.black_domains = data.get("black", [])
                    self.check_domains = data.get("check", [])
                    logger.info("[Storage] Настройки загружены из файла")
                    
                    if not self.white_domains:
                        self.white_domains = ["yandex.ru"]
                        logger.warning("[White List] Список пуст, установлен резервный домен")
                    
                    return
            except Exception as e:
                logger.error(f"Ошибка загрузки: {e}")
        
        self.reset_to_factory_logic()

    def reset_to_factory_logic(self):
        self.white_domains = [
            "rzd.ru", "vk.com", "yandex.ru", "sberbank.ru", 
            "gosuslugi.ru", "mts.ru", "beeline.ru", 
            "megafon.ru", "gazprom.ru", "lukoil.ru", 
            "aeroflot.ru", "post.ru", "rt.ru", "wildberries.ru", 
            "ozon.ru"
        ]
        self.check_domains = [
            "google.com", "cloudflare.com", 
            "microsoft.com", "amazon.com", "github.com", 
            "steamcommunity.com", "spotify.com", "netflix.com", 
            "wikipedia.org", "linkedin.com", "booking.com", 
            "airbnb.com", "paypal.com", "adobe.com", "zoom.us"
        ]
        self.black_domains = [
            "facebook.com", "instagram.com", "twitter.com", "tiktok.com", 
            "patreon.com", "soundcloud.com", "signal.org", 
            "viber.com", "roblox.com", "facetime.apple.com", "whatsapp.com", 
            "metacritic.com", "yourstoryinteractive.com", "ficbook.net", 
            "envato.com", "midjourney.com", "anthropic.com", "openai.com"
        ]
        logger.info("[Factory] Восстановлены заводские настройки")

    def save_settings_to_file(self, e=None):
        if not self.white_domains:
            self.white_domains = ["yandex.ru"]
            logger.warning("[Save] Белый список пуст, установлен резервный домен")
        
        data = {
            "white": self.white_domains,
            "black": self.black_domains,
            "check": self.check_domains
        }
        try:
            with open(self.get_settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Настройки успешно сохранены в файл!"), bgcolor="green"))
        except Exception as ex:
            logger.error(f"Ошибка сохранения: {ex}")
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Ошибка при сохранении"), bgcolor="red"))
        
        self.page.update()
    
    def handle_restore_btn(self, e):
        self.reset_to_factory_logic()
        self.page.overlay.clear()
        self.show_settings_sheet(None)
        self.page.show_snack_bar(ft.SnackBar(ft.Text("Списки сброшены к заводским (не забудьте сохранить!)")))
        self.page.update()
    
    def show_settings_sheet(self, e):
        white_tags = ft.Row(wrap=True, spacing=5)
        black_tags = ft.Row(wrap=True, spacing=5)
        check_tags = ft.Row(wrap=True, spacing=5)

        def create_chip(text, color, storage, container):
            chip = ft.Container(
                content=ft.Row([
                    ft.Text(text, size=11, color=color, weight="bold"),
                    ft.GestureDetector(
                        content=ft.Icon(ft.icons.CLOSE, size=14, color=color),
                        on_tap=lambda _: (storage.remove(text), container.controls.remove(chip), self.page.update())
                    )
                ], tight=True, spacing=5),
                padding=ft.padding.symmetric(horizontal=10, vertical=5),
                border=ft.border.all(1, color),
                border_radius=20,
                bgcolor=ft.colors.with_opacity(0.05, color)
            )
            return chip

        for d in self.white_domains:
            white_tags.controls.append(create_chip(d, ft.colors.GREEN_ACCENT, self.white_domains, white_tags))
        for d in self.black_domains:
            black_tags.controls.append(create_chip(d, ft.colors.RED_ACCENT, self.black_domains, black_tags))
        for d in self.check_domains:
            check_tags.controls.append(create_chip(d, ft.colors.AMBER_ACCENT, self.check_domains, check_tags))

        def create_input_field(label, color, storage, tags_container):
            text_field = ft.TextField(
                label=label,
                text_size=12,
                border_radius=15,
                border_color="#333333",
                focused_border_color=color,
                hint_text="Введите домен...",
                expand=True,
            )

            def add_domain(_):
                val = text_field.value.strip()
                if val and val not in storage:
                    storage.append(val)
                    tags_container.controls.append(create_chip(val, color, storage, tags_container))
                    text_field.value = ""
                    self.page.update()

            text_field.on_submit = add_domain
            
            return ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.ADD_CIRCLE_OUTLINE, color=color, size=24),
                    on_click=add_domain,
                    padding=ft.padding.only(left=5)
                ),
                text_field
            ], spacing=5)

        def get_full_list_view():
            def section(title, items, color):
                if not items:
                    return ft.Column([ft.Text(f"{title}: Список пуст", size=11, color=ft.colors.GREY_600)])
                domain_lines = [ft.Text(f"• {d}", size=11, color=color) for d in items]
                return ft.Column([
                    ft.Text(title, size=12, weight="bold", color=color),
                    ft.Column(domain_lines, spacing=2),
                    ft.Container(height=15)
                ], spacing=5)

            scrollable_content = ft.Container(
                content=ft.Column([
                    section("БЕЛЫЙ СПИСОК", self.white_domains, ft.colors.GREEN_ACCENT),
                    section("ДОМЕНЫ ДЛЯ ПРОВЕРКИ", self.check_domains, ft.colors.AMBER_ACCENT),
                    section("ЗАБЛОКИРОВАННЫЕ", self.black_domains, ft.colors.RED_ACCENT),
                ], scroll="adaptive"),
                height=350,
            )

            return ft.Column([
                ft.Text("ДЕТАЛЬНЫЙ СПИСОК ПРОВЕРКИ", weight="bold", size=16),
                ft.Divider(color="#222222"),
                scrollable_content,
                ft.Container(height=10),
                ft.ElevatedButton(
                    "ВЕРНУТЬСЯ В НАСТРОЙКИ", 
                    on_click=lambda _: self.show_settings_sheet(None),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                )
            ], horizontal_alignment="center", tight=True)

        def open_full_list(e):
            main_col.controls.clear()
            main_col.controls.append(get_full_list_view())
            self.page.update()

        white_block = create_input_field("Белый список", ft.colors.GREEN_ACCENT, self.white_domains, white_tags)
        black_block = create_input_field("Заблокированные", ft.colors.RED_ACCENT, self.black_domains, black_tags)
        check_block = create_input_field("Для проверки", ft.colors.AMBER_ACCENT, self.check_domains, check_tags)

        current_list_badge = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.LIST_ALT_ROUNDED, color=ft.colors.BLUE_ACCENT, size=16),
                ft.Text("Посмотреть текущий список", color=ft.colors.BLUE_ACCENT, size=12, weight="bold")
            ], tight=True),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border=ft.border.all(1, ft.colors.BLUE_ACCENT),
            border_radius=20,
            on_click=open_full_list
        )

        control_buttons = ft.Row([
            ft.IconButton(
                icon=ft.icons.REFRESH_ROUNDED, 
                icon_color=ft.colors.BLUE_ACCENT,
                tooltip="Сбросить к заводским", 
                on_click=self.handle_restore_btn
            ),
            ft.IconButton(
                icon=ft.icons.CHECK_CIRCLE_OUTLINE, 
                icon_color=ft.colors.GREEN_ACCENT,
                tooltip="Сохранить изменения в файл", 
                on_click=self.save_settings_to_file
            ),
        ], alignment="center", spacing=20)

        main_col = ft.Column([
            ft.Container(width=40, height=4, bgcolor="#333333", border_radius=10),
            ft.Text("Настройки тестирования", weight="bold", size=18),
            
            control_buttons,
            
            ft.Container(height=10),
            white_block, white_tags,
            ft.Container(height=5),
            black_block, black_tags,
            ft.Container(height=5),
            check_block, check_tags,
            ft.Container(height=20),
            current_list_badge,
            ft.Container(height=10),
        ], horizontal_alignment="center", tight=True, scroll="adaptive")

        sheet = ft.BottomSheet(
            ft.Container(main_col, padding=25, bgcolor="#0F0F0F", 
                        border_radius=ft.border_radius.only(top_left=25, top_right=25)),
            open=True,
            is_scroll_controlled=True
        )
        
        self.page.overlay.append(sheet)
        self.page.update()
                        
    def handle_button_hover(self, e):
        if e.data == "true":
            e.control.scale = self.hover_scale_factor  
            
            shadow_color = ft.colors.GREEN_ACCENT if self.hover_scale_factor > 1.1 else "#6366F1"
            e.control.shadow = ft.BoxShadow(
                blur_radius=25, 
                color=ft.colors.with_opacity(0.3, shadow_color),
                spread_radius=2
            )
            e.control.gradient = ft.LinearGradient(["#4F46E5", "#818CF8"])
        else:
            e.control.scale = 1.0
            e.control.shadow = None
            e.control.gradient = ft.LinearGradient(["#4338CA", "#6366F1"])
            
        e.control.update()

    def handle_verdict_hover(self, e):
        text_val = self.verdict_text.value.upper()
        
        if e.data == "true":
            if "СВОБОДНЫЙ" in text_val:
                e.control.bgcolor = "#0E3A1A"
                e.control.shadow = ft.BoxShadow(blur_radius=15, color=ft.colors.GREEN_ACCENT)
            else:
                e.control.bgcolor = "#3A0E0E"
                e.control.shadow = ft.BoxShadow(blur_radius=15, color=ft.colors.RED_ACCENT)
        else:
            e.control.shadow = None
            if "СВОБОДНЫЙ" in text_val:
                e.control.bgcolor = "#0A2410"
            else:
                e.control.bgcolor = "#240A0A"
            
        e.control.update()

    def show_details_sheet(self, e):
        # === ИСПРАВЛЕНО: ТЕПЕРЬ ОТРИСОВЫВАЕТ ВСЕ ДОМЕНЫ ИЗ ВСЕХ СПИСКОВ ГРУППИРОВАННО ===
        if not self.last_report:
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Сначала запустите тест!")))
            return

        grid = ft.GridView(
            expand=True,
            max_extent=130,
            child_aspect_ratio=1.0,
            spacing=10,
            run_spacing=10
        )
        
        availability = self.last_report.get('availability_data', [])
        
        # Группа 1: Заблокированные
        black_items = [item for item in availability if item.get('category') == 'black']
        for item in black_items:
            grid.controls.append(self._create_status_card(item))
        
        # Группа 2: Для проверки
        check_items = [item for item in availability if item.get('category') == 'check']
        for item in check_items:
            grid.controls.append(self._create_status_card(item))
        
        # Группа 3: Белый список
        white_items = [item for item in availability if item.get('category') == 'white']
        for item in white_items:
            grid.controls.append(self._create_status_card(item))
        
        sheet = ft.BottomSheet(
            ft.Container(
                content=ft.Column([
                    ft.Text("ДЕТАЛЬНЫЙ ОТЧЁТ", size=20, weight="bold"),
                    ft.Divider(),
                    grid
                ], expand=True),
                padding=20,
                height=500,
                bgcolor="#101010"
            )
        )
        self.page.overlay.append(sheet)
        sheet.open = True
        self.page.update()
    
    def _create_status_card(self, item):
        name = item.get('name', 'Unknown')
        status_raw = item.get('status', '').lower()
        
        is_ok = 'доступен' in status_raw
        status_text = "ДОСТУПЕН" if is_ok else status_raw.replace('_', ' ').title()
        status_color = ft.colors.GREEN_ACCENT if is_ok else ft.colors.RED_ACCENT
        icon = item.get('icon', '🌐')
        
        # === ИСПРАВЛЕНО: Убрал метку категории из карточки ===
        
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=30),
                ft.Text(name, weight="bold", size=12, text_align="center", max_lines=1),
                ft.Text(status_text, size=9, color=status_color, weight="bold"),
                # category_label удалён, теперь только название и статус
            ], alignment="center", horizontal_alignment="center", spacing=2),
            bgcolor="#161616",
            border=ft.border.all(1, "#333333"),
            border_radius=15,
            padding=10
        )

    def setup_page(self):
        self.page.title = "NetProfile: Deep Scan"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#0F0F0F"
        self.page.window_width = 420
        self.page.window_height = 850
        self.page.window_resizable = False
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.update()

    def setup_ui_components(self):
        self.stat_download = self.create_stat_block("Download", "0.0", ft.colors.GREEN_ACCENT, ft.icons.ARROW_DOWNWARD)
        self.stat_upload = self.create_stat_block("Upload", "0.0", ft.colors.PURPLE_ACCENT, ft.icons.ARROW_UPWARD)
        self.availability_list_scan = ft.Column(spacing=5, scroll="adaptive")

        self.stat_ping = ft.Container(
            content=self.create_stat_block("Ping", "0", ft.colors.YELLOW_ACCENT, ft.icons.TIMER),
            padding=5,
            border=ft.border.all(1, "#333333"),
            border_radius=10,
            bgcolor="#16161666" 
        )
        
        self.header_stats = ft.Row(
            controls=[self.stat_download, self.stat_upload, self.stat_ping],
            alignment=ft.MainAxisAlignment.SPACE_AROUND
        )

        self.quality_text = ft.Text("---", size=14)
        self.ping_btn = ft.Container(
            content=ft.TextButton("ПИНГ", on_click=self.update_only_ping, style=ft.ButtonStyle(color=ft.colors.BLUE_ACCENT)),
            border=ft.border.all(1, "#333333"),
            border_radius=10,
            bgcolor="#16161666",
            padding=ft.padding.only(left=5, right=5)
        )
        
        self.quality_row = ft.Container(
            content=ft.Row([
                ft.Row([ft.Icon(ft.icons.SIGNAL_CELLULAR_ALT, size=18, color=ft.colors.BLUE_200),
                        ft.Text("Качество связи: "), self.quality_text]),
                self.ping_btn
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.only(left=20, right=10)
        )

        self.radar_circle = ft.Container(
            content=ft.ProgressRing(width=100, height=100, stroke_width=4, color="#6366F1"),
            width=180, height=180, 
            shape=ft.BoxShape.CIRCLE,
            border=ft.border.all(3, "#333333"),
            alignment=ft.alignment.center,
            visible=False
        )

        self.main_button = ft.Container(
            content=ft.Text("НАЧАТЬ ТЕСТИРОВАНИЕ", weight="bold"),
            alignment=ft.alignment.center,
            width=260, height=70, border_radius=15,
            gradient=ft.LinearGradient(["#4338CA", "#6366F1"]),
            on_click=self.start_full_scan,
            animate_scale=300,
            on_hover=self.handle_button_hover
        )
        
        self.vpn_hint = ft.Text(
            "Включите VPN для лучшего анализа", 
            size=12, 
            color=ft.colors.GREY_600, 
            visible=False
        )

        self.verdict_text = ft.Text("", size=17, weight="bold", text_align="center")
        self.verdict_container = ft.Container(
            content=self.verdict_text, padding=15, border_radius=12,
            bgcolor="#161616", visible=False, on_hover=self.handle_verdict_hover
        )
        
        self.services_btn = ft.TextButton("Доступные сервисы", on_click=self.show_services_sheet, visible=False)

        self.services_btn = ft.Container(
           content=ft.Text("ДОСТУПНОСТЬ СЕРВИСОВ", size=13, color=ft.colors.GREY_400),
           on_click=self.show_details_sheet,
           visible=False
        )

        self.services_text = ft.Text(
            "Доступность сервисов", 
            size=14, 
            color=ft.colors.GREY_400,
        )
        
        def on_serv_hover(e):
            self.services_text.color = ft.colors.BLUE_400 if e.data == "true" else ft.colors.GREY_400
            self.services_text.update()

        self.services_btn = ft.Container(
            content=ft.GestureDetector(
                content=self.services_text,
                on_tap=self.show_details_sheet,
                on_hover=on_serv_hover, 
            ),
            visible=False,
            margin=ft.margin.only(top=10)
        )
                
        self.scan_view = ft.Column([
            ft.Container(height=10),
            self.header_stats,      
            ft.Divider(height=20, color="#222222"),
            self.quality_row,       
            
            ft.Container(expand=True), 
            
            ft.Column([
                self.main_button,   
                self.radar_circle,
                ft.Container(
                    content=self.vpn_hint,
                    on_click=lambda _: self.page.launch_url("https://google.com"), 
                    padding=5
                ),
            ], horizontal_alignment="center", spacing=10),

            ft.Container(expand=1),
            
            ft.Column([
                self.verdict_container,
                self.services_btn,
            ], horizontal_alignment="center", spacing=5),
                        
            ft.Container(expand=2), 
        ], horizontal_alignment="center", expand=True)

        self.res_list = ft.ListView(expand=True, spacing=10)
        self.res_view = ft.Container(content=ft.Column([ft.Text("Мировая доступность", size=20), self.res_list]), padding=20)
        self.log_list = ft.ListView(expand=True, spacing=5, padding=15)

        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="SCAN", icon=ft.icons.SATELLITE_ALT, content=self.scan_view),
                ft.Tab(text="RESOURCES", icon=ft.icons.LANGUAGE, content=self.res_view),
                ft.Tab(text="LOGS", icon=ft.icons.LIST_ALT, content=self.log_list),
            ],
            expand=True
        )

        self.settings_button = ft.IconButton(
            icon=ft.icons.SETTINGS_ROUNDED,
            icon_color=ft.colors.GREY_400,
            on_click=self.show_settings_sheet,
            icon_size=18,
            tooltip="Настройки",
            style=ft.ButtonStyle(
                padding=0,
            ),
            width=40,
            height=40,
        )

        self.layout = ft.Stack([
            self.tabs,
            ft.Container(
                content=self.settings_button,
                top=4,     
                right=0,   
            )
        ], expand=True)

        self.page.controls.clear()
        self.page.add(self.layout)
          
    async def update_only_ping(self, e):
        """Быстрое обновление ТОЛЬКО ICMP пинга по белому списку"""
        if not self.access_checker:
            from core.access_checker import AccessChecker
            self.access_checker = AccessChecker()
            self.access_checker.white_domains = self.white_domains
        
        self.quality_text.value = "Проверка..."
        self.page.update()

        current_white_list = self.white_domains if self.white_domains else ["yandex.ru"]
        
        # Получаем оба значения пинга
        icmp_ping, http_ping = await self.access_checker.run_pure_ping_test(current_white_list)
        
        stat_content = self.stat_ping.content
        if hasattr(stat_content, 'controls') and len(stat_content.controls) >= 2:
            self.stat_ping.content.controls[1].value = str(int(icmp_ping))  # Используем ICMP пинг!
        elif hasattr(stat_content, 'children') and len(stat_content.children) >= 2:
            self.stat_ping.content.children[1].value = str(int(icmp_ping))
        
        if icmp_ping == 0:
            self.quality_text.value = "Нет связи"
            self.quality_text.color = ft.colors.RED_ACCENT
        elif icmp_ping < 70:
            self.quality_text.value = "Отличное"
            self.quality_text.color = ft.colors.GREEN_ACCENT
        elif icmp_ping < 150:
            self.quality_text.value = "Нормальное"
            self.quality_text.color = ft.colors.BLUE_ACCENT
        else:
            self.quality_text.value = "Задержки"
            self.quality_text.color = ft.colors.ORANGE_ACCENT

        logger.info(f"[UI] Быстрый ICMP пинг белого списка ({len(current_white_list)} доменов): ICMP={icmp_ping}ms, HTTP={http_ping}ms")
        self.page.update()
        
    def show_services_sheet(self, e):
        grid = ft.GridView(expand=True, max_extent=150, child_aspect_ratio=1.0, spacing=10, run_spacing=10)
        
        if self.last_report and 'neutral_availability' in self.last_report:
            for item in self.last_report['neutral_availability']:
                grid.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(item['icon'], size=30),
                            ft.Text(item['name'], weight="bold", size=14, text_align="center"),
                            ft.Text(item['status'], size=10, 
                                    color=ft.colors.GREEN if item['status']=="Доступен" else ft.colors.RED)
                        ], alignment="center", horizontal_alignment="center"),
                        bgcolor="#1A1A1A", border=ft.border.all(1, "#333333"), border_radius=15
                    )
                )

        sheet = ft.BottomSheet(
            ft.Container(
                ft.Column([
                    ft.Container(width=40, height=4, bgcolor=ft.colors.GREY_800, border_radius=10),
                    ft.Text("Статус сервисов", weight="bold", size=18),
                    ft.Container(grid, height=400)
                ], horizontal_alignment="center", tight=True),
                padding=20, bgcolor="#0F0F0F", border_radius=ft.border_radius.only(top_left=20, top_right=20)
            ),
            open=True,
            enable_drag=True 
        )
        self.page.overlay.append(sheet)
        self.page.update()

    async def start_full_scan(self, e):   
        if self.speed_engine is None:
            try:
                from core.access_checker import AccessChecker
                from core.report_gen import ReportGenerator
                from core.speed_engine import SpeedEngine
                from core.dpi_probe import DPIProbe
                
                self.access_checker = AccessChecker()
                self.access_checker.white_domains = self.white_domains
                self.access_checker.check_domains = self.check_domains
                self.access_checker.black_domains = self.black_domains
                self.report_gen = ReportGenerator()
                self.speed_engine = SpeedEngine()
                self.dpi_probe = DPIProbe()
            except Exception as err:
                logger.error(f"Ошибка загрузки модулей core: {err}")
                self.page.show_snack_bar(ft.SnackBar(ft.Text(f"Ошибка ядра: {err}"), bgcolor="red"))
                return

        self.main_button.visible = False
        self.verdict_container.visible = False
        self.services_btn.visible = False
        self.radar_circle.visible = True
        self.page.update()

        try:
            logger.info("=== ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ ===")
            
            # === ОТЛАДКА: ПРОВЕРКА НАСТРОЕК ===
            logger.info(f"[MAIN] white_domains count: {len(self.white_domains)}")
            logger.info(f"[MAIN] check_domains count: {len(self.check_domains)}")
            logger.info(f"[MAIN] black_domains count: {len(self.black_domains)}")
            # ============================================
            
            speed_data_task = asyncio.create_task(self.speed_engine.run_full_test(white_domains_list=self.white_domains))
            white_test_task = asyncio.create_task(self.access_checker.run_white_list_test())
            check_test_task = asyncio.create_task(self.access_checker.run_check_list_test())
            black_test_task = asyncio.create_task(self.access_checker.run_black_list_test())
            dpi_test_task = asyncio.create_task(self.dpi_probe.run_dpi_test())
            
            speed_data = await speed_data_task
            white_data = await white_test_task
            check_data = await check_test_task
            black_data = await black_test_task
            dpi_res = await dpi_test_task
            
            logger.info(f"[ACCESS] Получено данных: Белые={len(white_data.get('availability_data', []))}, Проверка={len(check_data.get('availability_data', []))}, Заблокированы={len(black_data.get('availability_data', []))}")
            
            report = self.report_gen.analyze(white_data, check_data, black_data, dpi_res)

            self.last_report = report

            dl_value = speed_data.get('avg_speed', 0.0)
            ul_value = speed_data.get('upload_speed', 0.0)
            
            # === ИСПРАВЛЕНО: Используем HTTP пинг при полном тестировании ===
            ping_value = int(report.get('metrics', {}).get('ping_http', 0))
            
            logger.info(f"[PING] HTTP Average Ping: {ping_value}ms, Download={dl_value}, Upload={ul_value}")
            
            if hasattr(self, 'stat_download'):
                if hasattr(self.stat_download, 'controls') and len(self.stat_download.controls) >= 2:
                    self.stat_download.controls[1].value = f"{dl_value:.1f}"
                elif hasattr(self.stat_download, 'children') and len(self.stat_download.children) >= 2:
                    self.stat_download.children[1].value = f"{dl_value:.1f}"
            
            if hasattr(self, 'stat_upload'):
                if hasattr(self.stat_upload, 'controls') and len(self.stat_upload.controls) >= 2:
                    self.stat_upload.controls[1].value = f"{ul_value:.1f}"
                elif hasattr(self.stat_upload, 'children') and len(self.stat_upload.children) >= 2:
                    self.stat_upload.children[1].value = f"{ul_value:.1f}"
            
            if hasattr(self, 'stat_ping') and hasattr(self.stat_ping, 'content'):
                stat_content = self.stat_ping.content
                if hasattr(stat_content, 'controls') and len(stat_content.controls) >= 2:
                    stat_content.controls[1].value = str(ping_value)
                elif hasattr(stat_content, 'children') and len(stat_content.children) >= 2:
                    stat_content.children[1].value = str(ping_value)
                
                p = ping_value
                if p == 0: q_text, q_col = "---", ft.colors.GREY_400
                elif p < 70: q_text, q_col = "Отличное", ft.colors.GREEN_ACCENT
                elif p < 150: q_text, q_col = "Хорошее", ft.colors.BLUE_ACCENT
                else: q_text, q_col = "Нестабильное", ft.colors.ORANGE_ACCENT
                
                if hasattr(self, 'quality_text'):
                    self.quality_text.value = q_text
                    self.quality_text.color = q_col
            
                        # === ИСПРАВЛЕНО: Корректная отрисовка ВСЕХ ресурсов без пропуска ===
                        # === ИСПРАВЛЕНО: Корректная отрисовка ВСЕХ ресурсов без пропуска ===
            raw_resources = report.get('availability_data', [])
            logger.info(f"[RESOURCES] Всего найдено {len(raw_resources)} элементов доступности")
            
            all_resources = []
            seen_keys = set() # Используем ключ (имя_категория) для уникальности
            
            if isinstance(raw_resources, list):
                for r in raw_resources:
                    if isinstance(r, dict) and 'name' in r:
                        name = r['name']
                        category = r.get('category', 'unknown')
                        
                        # Уникальный ключ: имя + категория
                        unique_key = f"{name}_{category}"
                        
                        if unique_key not in seen_keys:
                            seen_keys.add(unique_key)
                            all_resources.append(r)
                            logger.debug(f"[DEBUG] Добавлен ресурс: {name} ({category})")
                        else:
                            logger.warning(f"[DEBUG] Пропущен дубликат: {name} ({category})")
            
            logger.info(f"[RESOURCES] После фильтрации дублей: {len(all_resources)} элементов")

            if hasattr(self, 'res_list'):
                self.res_list.controls.clear()
                
                for item in all_resources:
                    name = item.get('name', 'Unknown')
                    display_status = item.get('status', 'Неизвестно')
                    
                    # Просто выводим имя, метки убраны
                    self.res_list.controls.append(self.create_domain_card(name, display_status))
                
                self.res_list.update()
                logger.info(f"[UI] Отрисовано {len(self.res_list.controls)} карточек ресурсов")

                        # === ИСПРАВЛЕНО: КОРРЕКТНАЯ ЛОГИКА ВЕРДИКТОВ (ИСПОЛЬЗУЕМ ДАННЫЕ ИЗ ОТЧЕТА) ===
            statistics = report.get('statistics', {})
            
            # Получаем значения напрямую из статистики отчета
            white_accessible_count = statistics.get('white_accessible_count', 0)
            white_total_count = statistics.get('white_total', 0)
            white_rate = statistics.get('white_rate', 0.0)
            
            check_accessible_count = statistics.get('check_accessible_count', 0)
            check_total_count = statistics.get('check_total', 0) # <--- ДОБАВИТЬ ЭТУ СТРОКУ
            check_rate = statistics.get('check_rate', 0.0)
            
            # === ОТЛАДКА: ПОКАЗЫВАЕМ, ЧТО ВИДИТ ПРОГРАММА ===
            logger.info(f"=== ОТЛАДКА ДАННЫХ ===")
            logger.info(f"[WHITE] Всего доменов: {white_total_count}, Доступно: {white_accessible_count}")
            logger.info(f"[WHITE] Расчетный процент (w_rate): {white_rate:.2f} ({int(white_rate*100)}%)")
            
            logger.info(f"[CHECK] Всего доменов: {check_total_count}, Доступно: {check_accessible_count}")
            logger.info(f"[CHECK] Расчетный процент (c_rate): {check_rate:.2f} ({int(check_rate*100)}%)")
            
            if white_total_count == 0:
                logger.warning("[WHITE] ОШИБКА: Белый список пуст! w_rate будет 0.")
            if check_total_count == 0:
                logger.warning("[CHECK] ОШИБКА: Список проверки пуст! c_rate будет 0.")
            # ============================================
            
            # === ИСПРАВЛЕНО: ИСПОЛЬЗУЕМ ГОТОВЫЙ ВЕРДИКТ ИЗ ОТЧЕТА ===
            zone_status = report.get('zone_status', 'Неизвестно')
            
            # Маппинг статусов из зоны в текст для UI
            if zone_status == "СЕТЬ НЕДОСТУПНА / ФАТАЛЬНЫЙ СБОЙ":
                status_text = "НЕТ ДОСТУПА К ИНТЕРНЕТУ"
                color_theme = ft.colors.RED_ACCENT
                bg_color = "#240A0A"
                
            elif zone_status == "РЕЖИМ БЕЛЫХ СПИСКОВ (Блокировка внешнего сегмента)":
                status_text = "ЗОНА БЕЛЫХ СПИСКОВ"
                color_theme = ft.colors.ORANGE_ACCENT
                bg_color = "#24160A"
                
            elif zone_status == "СВОБОДНЫЙ ДОСТУП (Фильтры не обнаружены)":
                status_text = "СВОБОДНЫЙ ДОСТУП"
                color_theme = ft.colors.GREEN_ACCENT
                bg_color = "#0A2410"
                
            elif zone_status == "ЗОНА ЧАСТИЧНОЙ ФИЛЬТРАЦИИ (Обнаружен DPI)":
                status_text = "ЗОНА ЧАСТИЧНЫХ ОГРАНИЧЕНИЙ"
                color_theme = ft.colors.AMBER_ACCENT
                bg_color = "#241B0A"
                
            else:
                # На всякий случай fallback
                status_text = "НЕИЗВЕСТНО"
                color_theme = ft.colors.GREY_500
                bg_color = "#242424"

            self.verdict_text.value = status_text
            self.verdict_text.color = color_theme
            self.verdict_container.bgcolor = bg_color 
            self.verdict_container.border = ft.border.all(2, color_theme)
            
            self.radar_circle.visible = False
            self.main_button.visible = True
            self.verdict_container.visible = True
            self.services_btn.visible = True if status_text != "СВОБОДНЫЙ ДОСТУП" else False
            self.page.update()

            logger.info(f"=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО === Вердикт: {status_text} (Статус ядра: {zone_status})")    

        except Exception as ex:
            logger.error(f"Ошибка анализа: {ex}")
            import traceback
            logger.error(traceback.format_exc())
            self.page.show_snack_bar(ft.SnackBar(ft.Text(f"ОШИБКА: {str(ex)}"), bgcolor="red"))
            self.radar_circle.visible = False
            self.main_button.visible = True
            self.verdict_container.visible = True
            self.page.update()   
            
        finally:
            self.radar_circle.visible = False
            self.main_button.visible = True
            if hasattr(self, 'vpn_hint'):
                self.vpn_hint.visible = True
            self.verdict_container.visible = True
            self.page.update()       
                  
    def create_stat_block(self, label, value, color, icon):
        return ft.Column([
            ft.Icon(icon, color=color, size=28), 
            ft.Text(value, size=22, weight="bold", color=color), 
            ft.Text(label, size=11, color=ft.colors.GREY_500)
        ], horizontal_alignment="center", spacing=5)

    def create_domain_card(self, name, status):
       dot_color = ft.colors.GREEN_ACCENT if "доступен" in status.lower() else ft.colors.RED_ACCENT
    
       return ft.Container(
           content=ft.Row([
               ft.Icon(ft.icons.LANGUAGE, color=ft.colors.BLUE_GREY_400, size=20),
               ft.Text(name, size=14, weight=ft.FontWeight.W_500, expand=True),
               ft.Text(status, size=12, color=dot_color),
               ft.Container(width=10, height=10, bgcolor=dot_color, border_radius=5)
           ]),
           padding=10,
           border=ft.border.all(1, ft.colors.GREY_800),
           border_radius=8,
           margin=ft.margin.only(bottom=5)
       )    
    
async def main(page: ft.Page):
    # 1. Базовая настройка (минимализм)
    page.theme_mode = ft.ThemeMode.DARK
    page.window_visible = True # Явно просим показать окно
    
    # 2. Показываем заглушку сразу
    loading_text = ft.Text("Загрузка DeepScan...")
    page.add(loading_text)
    page.update()

    # 3. Делаем небольшую паузу, чтобы Android "прожевал" графику
    import asyncio
    await asyncio.sleep(1)

    try:
        # Здесь твой основной код добавления кнопок и логов
        page.controls.remove(loading_text)
        page.add(ft.Text("Система готова!"))
        # ... твой UI ...
    except Exception as e:
        page.add(ft.Text(f"Ошибка: {e}", color="red"))
    
    page.update()

if __name__ == "__main__":
    # Вызываем приложение без лишних параметров
    ft.app(target=main)
