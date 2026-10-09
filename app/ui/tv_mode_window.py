import os
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QFrame,
    QProgressBar, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QTime, Signal, QEvent
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QKeyEvent
from PySide6.QtMultimedia import QMediaPlayer

from app.core.database import MediaDatabase
from app.core.config import AppConfig
from app.core.tv_schedule import TVScheduleManager, TVChannel, ScheduleItem
from app.ui.tv_player_widget import TVPlayerWidget
from app.ui.channel_config_dialog import ChannelConfigDialog


class TVModeWindow(QMainWindow):
    """Janela do Modo TV com canais temáticos, grade de 24h, animação OSD e player integrado."""

    def __init__(self, db: MediaDatabase, config: AppConfig, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config

        self.setWindowTitle("📺 MediaFinder TV Network — Modo TV & Programação")
        self.resize(1200, 720)
        self.setMinimumSize(800, 500)

        self.schedule_mgr = TVScheduleManager(self.db, self.config)
        self.current_channel_idx = 0
        self.current_playing_item: Optional[ScheduleItem] = None

        self._init_ui()
        self._setup_shortcuts()

        # Gera grade do dia
        self.schedule_mgr.build_schedules_for_today()
        self._populate_channels_ui()

        # Timer do relógio e sincronização EPG a cada 1 segundo
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock_and_epg)
        self.clock_timer.start(1000)

        # Inicia reprodução do primeiro canal
        QTimer.singleShot(300, lambda: self._select_channel(0))

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # 1. Top Bar Estilo Emissora de TV
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #12151B; border-bottom: 1px solid #242A34; padding: 4px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)

        lbl_logo = QLabel("📺 MediaFinder TV")
        lbl_logo.setStyleSheet("font-size: 16px; font-weight: bold; color: #38BDF8;")
        top_layout.addWidget(lbl_logo)

        self.lbl_channel_tag = QLabel("CH 01 — Cinema & Filmes")
        self.lbl_channel_tag.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: 600; padding-left: 10px;")
        top_layout.addWidget(self.lbl_channel_tag)

        top_layout.addStretch()

        # Relógio Digital em tempo real
        self.lbl_clock = QLabel("00:00:00")
        self.lbl_clock.setStyleSheet("font-size: 14px; font-weight: bold; color: #A855F7; font-family: monospace;")
        top_layout.addWidget(self.lbl_clock)

        # Botão para Gerenciar Canais e Pastas
        self.btn_config_channels = QPushButton("⚙️ Configurar Canais (C)")
        self.btn_config_channels.setStyleSheet("padding: 5px 12px; font-size: 11px; font-weight: bold; background-color: #1E293B; color: #38BDF8; border: 1px solid #38BDF8; border-radius: 4px;")
        self.btn_config_channels.setToolTip("Criar, editar ou escolher pastas e modos (Aleatório/Sequencial) dos canais (Tecla C)")
        self.btn_config_channels.clicked.connect(self.open_channel_config_dialog)
        top_layout.addWidget(self.btn_config_channels)

        # Botão para Gerar Nova Grade Aleatória de Todos os Canais
        self.btn_regenerate_schedule = QPushButton("🎲 Nova Grade (R)")
        self.btn_regenerate_schedule.setObjectName("primary_action_btn")
        self.btn_regenerate_schedule.setStyleSheet("padding: 5px 12px; font-size: 11px; font-weight: bold;")
        self.btn_regenerate_schedule.setToolTip("Gera uma nova programação do zero para todos os canais ao vivo (Tecla R)")
        self.btn_regenerate_schedule.clicked.connect(self.regenerate_all_schedules)
        top_layout.addWidget(self.btn_regenerate_schedule)

        # Botão para Ocultar / Mostrar Grade e Canais
        self.btn_toggle_sidebar = QPushButton("📑 Ocultar Grade (G)")
        self.btn_toggle_sidebar.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        self.btn_toggle_sidebar.setToolTip("Ocultar ou Exibir painel lateral de canais e programação (Tecla G)")
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        top_layout.addWidget(self.btn_toggle_sidebar)

        # Botões de Canal
        self.btn_ch_prev = QPushButton("◀ CH-")
        self.btn_ch_prev.clicked.connect(self._prev_channel)
        top_layout.addWidget(self.btn_ch_prev)

        self.btn_ch_next = QPushButton("CH+ ▶")
        self.btn_ch_next.clicked.connect(self._next_channel)
        top_layout.addWidget(self.btn_ch_next)

        # Botão Fechar TV
        self.btn_exit_tv = QPushButton("✕ Sair do Modo TV")
        self.btn_exit_tv.clicked.connect(self.close)
        top_layout.addWidget(self.btn_exit_tv)

        main_layout.addWidget(top_bar)

        # 2. Splitter (Player à esquerda, Grade / EPG à direita)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)

        # Player Widget
        self.player_widget = TVPlayerWidget(self)
        self.player_widget.playback_finished.connect(self._play_next_scheduled_item)
        self.player_widget.fullscreen_requested.connect(self._toggle_fullscreen)
        self.player_widget.duration_resolved.connect(self._on_media_duration_resolved)
        self.splitter.addWidget(self.player_widget)

        # Painel Lateral EPG (Grade de Programação)
        self.epg_panel = QFrame()
        self.epg_panel.setStyleSheet("background-color: #15181E; border: 1px solid #242A34; border-radius: 8px;")
        epg_layout = QVBoxLayout(self.epg_panel)
        epg_layout.setContentsMargins(10, 10, 10, 10)
        epg_layout.setSpacing(8)

        # Seletor Rápido de Canais
        lbl_channels_title = QLabel("📡 CANAIS DISPONÍVEIS")
        lbl_channels_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #94A3B8; letter-spacing: 1px;")
        epg_layout.addWidget(lbl_channels_title)

        self.channel_btn_layout = QHBoxLayout()
        self.channel_btn_layout.setSpacing(4)
        epg_layout.addLayout(self.channel_btn_layout)

        # Cartão "No Ar Agora"
        now_card = QFrame()
        now_card.setStyleSheet("background-color: #1A202C; border: 1px solid #3B82F6; border-radius: 6px; padding: 6px;")
        now_card_layout = QVBoxLayout(now_card)
        now_card_layout.setSpacing(4)

        lbl_now_header = QLabel("🔴 NO AR NESTE MOMENTO")
        lbl_now_header.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")
        now_card_layout.addWidget(lbl_now_header)

        self.lbl_now_title = QLabel("Aguardando carregamento...")
        self.lbl_now_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF;")
        self.lbl_now_title.setWordWrap(True)
        now_card_layout.addWidget(self.lbl_now_title)

        self.lbl_now_time_range = QLabel("00:00 - 00:00")
        self.lbl_now_time_range.setStyleSheet("font-size: 11px; color: #38BDF8;")
        now_card_layout.addWidget(self.lbl_now_time_range)

        epg_layout.addWidget(now_card)

        # Lista de Próximos Programas da Grade
        lbl_sched_title = QLabel("📅 GRADE DE PROGRAMAÇÃO DO DIA (24H)")
        lbl_sched_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #94A3B8; letter-spacing: 1px;")
        epg_layout.addWidget(lbl_sched_title)

        self.schedule_list = QListWidget()
        self.schedule_list.setStyleSheet("""
            QListWidget {
                background-color: #0E1014;
                border: 1px solid #1E242D;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #1A1F26;
            }
            QListWidget::item:hover {
                background-color: #1A202C;
            }
            QListWidget::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)
        self.schedule_list.itemDoubleClicked.connect(self._on_schedule_item_clicked)
        epg_layout.addWidget(self.schedule_list, 1)

        # Botão Ação Próximo Episódio
        self.btn_next_ep = QPushButton("⏭ Assistir Próximo Programa")
        self.btn_next_ep.setObjectName("primary_action_btn")
        self.btn_next_ep.clicked.connect(self._play_next_scheduled_item)
        epg_layout.addWidget(self.btn_next_ep)

        self.splitter.addWidget(self.epg_panel)

        # Proporções: 65% Player, 35% Grade
        self.splitter.setStretchFactor(0, 65)
        self.splitter.setStretchFactor(1, 35)

        main_layout.addWidget(self.splitter, 1)

    def _setup_shortcuts(self):
        """Atalhos interativos do Modo TV (Teclas de Canal, Volume, Grade, Regenerar, Configurar e Tela Cheia)."""
        # Reprodução e Tela Cheia
        QShortcut(QKeySequence("Space"), self, activated=self.player_widget.toggle_play_pause)
        QShortcut(QKeySequence("F11"), self, activated=lambda: self._toggle_fullscreen(not self.isFullScreen()))
        QShortcut(QKeySequence("F"), self, activated=lambda: self._toggle_fullscreen(not self.isFullScreen()))
        QShortcut(QKeySequence("Esc"), self, activated=self._on_escape_pressed)

        # Configurar Canais
        QShortcut(QKeySequence("C"), self, activated=self.open_channel_config_dialog)

        # Regenerar Nova Grade Aleatória do Dia
        QShortcut(QKeySequence("R"), self, activated=self.regenerate_all_schedules)
        QShortcut(QKeySequence("F5"), self, activated=self.regenerate_all_schedules)

        # Ocultar / Mostrar Barra Lateral (Grade de Canais)
        QShortcut(QKeySequence("G"), self, activated=self.toggle_sidebar)
        QShortcut(QKeySequence("Tab"), self, activated=self.toggle_sidebar)

        # Navegação de Canais (Page Up/Down e Setas Esquerda/Direita)
        QShortcut(QKeySequence("Page_Up"), self, activated=self._next_channel)
        QShortcut(QKeySequence("Page_Down"), self, activated=self._prev_channel)
        QShortcut(QKeySequence("Right"), self, activated=self._next_channel)
        QShortcut(QKeySequence("Left"), self, activated=self._prev_channel)

        # Controle de Volume Vintage OSD (+/- e Setas Cima/Baixo)
        QShortcut(QKeySequence("Up"), self, activated=lambda: self.player_widget.set_volume_relative(+5))
        QShortcut(QKeySequence("Down"), self, activated=lambda: self.player_widget.set_volume_relative(-5))
        QShortcut(QKeySequence("+"), self, activated=lambda: self.player_widget.set_volume_relative(+5))
        QShortcut(QKeySequence("="), self, activated=lambda: self.player_widget.set_volume_relative(+5))
        QShortcut(QKeySequence("-"), self, activated=lambda: self.player_widget.set_volume_relative(-5))
        QShortcut(QKeySequence("M"), self, activated=self.player_widget.toggle_mute)

        # Alternar Faixa de Áudio (Dual Áudio) e Legendas
        QShortcut(QKeySequence("A"), self, activated=self.player_widget.cycle_audio_track)
        QShortcut(QKeySequence("S"), self, activated=self.player_widget.cycle_subtitle_track)
        QShortcut(QKeySequence("L"), self, activated=self.player_widget.cycle_subtitle_track)

        # Atalhos Numéricos Diretos de Canais (1 a 9)
        for num in range(1, 10):
            QShortcut(QKeySequence(str(num)), self, activated=lambda n=num: self._tune_number_direct(n))

        # Teclas Multimídia de Teclados Dedicados
        try:
            QShortcut(QKeySequence(Qt.Key_MediaPlay), self, activated=self.player_widget.toggle_play_pause)
            QShortcut(QKeySequence(Qt.Key_MediaPause), self, activated=self.player_widget.toggle_play_pause)
            QShortcut(QKeySequence(Qt.Key_MediaTogglePlayPause), self, activated=self.player_widget.toggle_play_pause)
            QShortcut(QKeySequence(Qt.Key_MediaStop), self, activated=self.player_widget.stop)
            QShortcut(QKeySequence(Qt.Key_MediaNext), self, activated=self._next_channel)
            QShortcut(QKeySequence(Qt.Key_MediaPrevious), self, activated=self._prev_channel)
            QShortcut(QKeySequence(Qt.Key_VolumeUp), self, activated=lambda: self.player_widget.set_volume_relative(+5))
            QShortcut(QKeySequence(Qt.Key_VolumeDown), self, activated=lambda: self.player_widget.set_volume_relative(-5))
            QShortcut(QKeySequence(Qt.Key_VolumeMute), self, activated=self.player_widget.toggle_mute)
        except Exception:
            pass

        # Instala filtro de eventos em todos os componentes para captura de teclas
        self.installEventFilter(self)
        if hasattr(self, 'player_widget'):
            self.player_widget.installEventFilter(self)
            if hasattr(self.player_widget, 'video_widget'):
                self.player_widget.video_widget.installEventFilter(self)
        if hasattr(self, 'schedule_list'):
            self.schedule_list.installEventFilter(self)
        if hasattr(self, 'epg_panel'):
            self.epg_panel.installEventFilter(self)

    def eventFilter(self, watched, event: QEvent) -> bool:
        """Garante que as setas do teclado, teclas multimídia e atalhos funcionem de qualquer foco na janela da TV."""
        if event.type() == QEvent.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            if key in (Qt.Key_Up, Qt.Key_VolumeUp):
                self.player_widget.set_volume_relative(+5)
                return True
            elif key in (Qt.Key_Down, Qt.Key_VolumeDown):
                self.player_widget.set_volume_relative(-5)
                return True
            elif key in (Qt.Key_Right, Qt.Key_PageUp, Qt.Key_MediaNext):
                self._next_channel()
                return True
            elif key in (Qt.Key_Left, Qt.Key_PageDown, Qt.Key_MediaPrevious):
                self._prev_channel()
                return True
            elif key in (Qt.Key_Space, Qt.Key_MediaPlay, Qt.Key_MediaPause, Qt.Key_MediaTogglePlayPause):
                self.player_widget.toggle_play_pause()
                return True
            elif key == Qt.Key_MediaStop:
                self.player_widget.stop()
                return True
            elif key in (Qt.Key_F11, Qt.Key_F):
                self._toggle_fullscreen(not self.isFullScreen())
                return True
            elif key == Qt.Key_Escape:
                self._on_escape_pressed()
                return True
            elif key in (Qt.Key_G, Qt.Key_Tab):
                self.toggle_sidebar()
                return True
            elif key == Qt.Key_C:
                self.open_channel_config_dialog()
                return True
            elif key in (Qt.Key_R, Qt.Key_F5):
                self.regenerate_all_schedules()
                return True
            elif key == Qt.Key_A:
                self.player_widget.cycle_audio_track()
                return True
            elif key in (Qt.Key_S, Qt.Key_L):
                self.player_widget.cycle_subtitle_track()
                return True
            elif key in (Qt.Key_M, Qt.Key_VolumeMute):
                self.player_widget.toggle_mute()
                return True
            elif Qt.Key_1 <= key <= Qt.Key_9:
                num = key - Qt.Key_1 + 1
                self._tune_number_direct(num)
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_VolumeUp):
            self.player_widget.set_volume_relative(+5)
            event.accept()
            return
        elif key in (Qt.Key_Down, Qt.Key_VolumeDown):
            self.player_widget.set_volume_relative(-5)
            event.accept()
            return
        elif key in (Qt.Key_Right, Qt.Key_PageUp, Qt.Key_MediaNext):
            self._next_channel()
            event.accept()
            return
        elif key in (Qt.Key_Left, Qt.Key_PageDown, Qt.Key_MediaPrevious):
            self._prev_channel()
            event.accept()
            return
        elif key in (Qt.Key_Space, Qt.Key_MediaPlay, Qt.Key_MediaPause, Qt.Key_MediaTogglePlayPause):
            self.player_widget.toggle_play_pause()
            event.accept()
            return
        elif key == Qt.Key_MediaStop:
            self.player_widget.stop()
            event.accept()
            return
        elif key in (Qt.Key_F11, Qt.Key_F):
            self._toggle_fullscreen(not self.isFullScreen())
            event.accept()
            return
        elif key == Qt.Key_Escape:
            self._on_escape_pressed()
            event.accept()
            return
        elif key in (Qt.Key_G, Qt.Key_Tab):
            self.toggle_sidebar()
            event.accept()
            return
        elif key == Qt.Key_C:
            self.open_channel_config_dialog()
            event.accept()
            return
        elif key in (Qt.Key_R, Qt.Key_F5):
            self.regenerate_all_schedules()
            event.accept()
            return
        elif key == Qt.Key_A:
            self.player_widget.cycle_audio_track()
            event.accept()
            return
        elif key in (Qt.Key_S, Qt.Key_L):
            self.player_widget.cycle_subtitle_track()
            event.accept()
            return
        elif key in (Qt.Key_M, Qt.Key_VolumeMute):
            self.player_widget.toggle_mute()
            event.accept()
            return
        elif Qt.Key_1 <= key <= Qt.Key_9:
            num = key - Qt.Key_1 + 1
            self._tune_number_direct(num)
            event.accept()
            return
        super().keyPressEvent(event)

    def open_channel_config_dialog(self):
        """Abre o diálogo de gerenciamento de canais personalizados."""
        dialog = ChannelConfigDialog(self.config, self.db, self)
        dialog.channels_updated.connect(self._on_channels_reconfigured)
        dialog.exec()


    def _on_channels_reconfigured(self):
        """Atualiza a grade e interface quando canais forem criados/editados pelo usuário."""
        self.schedule_mgr.load_channels_from_config()
        self.schedule_mgr.build_schedules_for_today()
        self._populate_channels_ui()
        target_idx = min(self.current_channel_idx, len(self.schedule_mgr.channels) - 1) if self.schedule_mgr.channels else 0
        self._select_channel(target_idx)

    def _on_media_duration_resolved(self, file_path: str, duration_sec: int):
        """Atualiza a grade com a duração real do arquivo sem interromper a transmissão."""
        if duration_sec > 0:
            try:
                self.schedule_mgr.db.update_file_duration(file_path, duration_sec)
            except Exception:
                pass

        if not self.current_playing_item or self.current_playing_item.file_path != file_path:
            return

        if abs(self.current_playing_item.duration_seconds - duration_sec) > 5:
            self.current_playing_item.update_duration(duration_sec)
            self.lbl_now_time_range.setText(f"Horário de Exibição: {self.current_playing_item.display_time}")

            # Reajusta os horários de início e término dos itens subsequentes na grade do canal
            if self.schedule_mgr.channels and 0 <= self.current_channel_idx < len(self.schedule_mgr.channels):
                channel = self.schedule_mgr.channels[self.current_channel_idx]
                try:
                    curr_idx = channel.schedule.index(self.current_playing_item)
                    next_start = self.current_playing_item.end_dt
                    for i in range(curr_idx + 1, len(channel.schedule)):
                        sub_item = channel.schedule[i]
                        sub_item.start_dt = next_start
                        sub_item.end_dt = next_start + timedelta(seconds=sub_item.duration_seconds)
                        next_start = sub_item.end_dt
                    self._populate_schedule_list(channel)
                except Exception:
                    pass

    def regenerate_all_schedules(self):
        """Gera uma grade de programação completamente nova para todos os canais."""
        self.schedule_mgr.build_schedules_for_today(randomize=True)
        if self.schedule_mgr.channels:
            channel = self.schedule_mgr.channels[self.current_channel_idx]
            self._populate_schedule_list(channel)
            self._tune_current_program(channel)

    def toggle_sidebar(self):
        """Oculta ou exibe o painel lateral com os canais e a programação diária."""
        visible = not self.epg_panel.isVisible()
        self.epg_panel.setVisible(visible)
        if visible:
            self.btn_toggle_sidebar.setText("📑 Ocultar Grade (G)")
            self.splitter.setSizes([int(self.width() * 0.65), int(self.width() * 0.35)])
        else:
            self.btn_toggle_sidebar.setText("📑 Mostrar Grade (G)")
            self.splitter.setSizes([self.width(), 0])

    def _tune_number_direct(self, number: int):
        target_idx = number - 1
        if 0 <= target_idx < len(self.schedule_mgr.channels):
            self._select_channel(target_idx)

    def _on_escape_pressed(self):
        if self.isFullScreen():
            self._toggle_fullscreen(False)
        else:
            self.close()

    def _toggle_fullscreen(self, enable: bool):
        if enable:
            self.showFullScreen()
        else:
            self.showNormal()

    def _populate_channels_ui(self):
        # Limpa botões existentes
        for i in reversed(range(self.channel_btn_layout.count())):
            w = self.channel_btn_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        self.channel_buttons = []
        for idx, ch in enumerate(self.schedule_mgr.channels):
            btn = QPushButton(f"{ch.icon} {ch.name.split('(')[0].strip()}")
            btn.setStyleSheet("""
                QPushButton {
                    padding: 5px 8px;
                    font-size: 11px;
                    border-radius: 4px;
                }
            """)
            btn.clicked.connect(lambda _, ch_idx=idx: self._select_channel(ch_idx))
            self.channel_btn_layout.addWidget(btn)
            self.channel_buttons.append(btn)

    def _select_channel(self, channel_idx: int):
        if not self.schedule_mgr.channels:
            return

        self.current_channel_idx = channel_idx % len(self.schedule_mgr.channels)
        channel = self.schedule_mgr.channels[self.current_channel_idx]

        mode_badge = " [🎲 Aleatório]" if channel.mode == "random" else " [🔢 Sequencial]"
        self.lbl_channel_tag.setText(f"CH {channel.number:02d} — {channel.name}{mode_badge}")

        # Atualiza estilo dos botões
        for idx, btn in enumerate(self.channel_buttons):
            if idx == self.current_channel_idx:
                btn.setStyleSheet("background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 5px 8px;")
            else:
                btn.setStyleSheet("background-color: #1E232B; color: #94A3B8; border-radius: 4px; padding: 5px 8px;")

        self._populate_schedule_list(channel)
        self._tune_current_program(channel)

    def _populate_schedule_list(self, channel: TVChannel):
        self.schedule_list.clear()
        now = datetime.now()

        for item in channel.schedule:
            time_str = item.display_time
            title_str = item.full_display_title
            
            is_live = (item.start_dt <= now < item.end_dt)
            prefix = "🔴 NO AR: " if is_live else ""
            
            list_item = QListWidgetItem(f"[{time_str}] {prefix}{title_str}")
            list_item.setData(Qt.UserRole, item)

            if is_live:
                list_item.setForeground(Qt.cyan)
                font = list_item.font()
                font.setBold(True)
                list_item.setFont(font)

            self.schedule_list.addItem(list_item)

    def _tune_current_program(self, channel: TVChannel):
        now = datetime.now()
        current_item = channel.get_current_item(now)
        if current_item:
            self.current_playing_item = current_item
            self.lbl_now_title.setText(current_item.full_display_title)
            self.lbl_now_time_range.setText(f"Horário de Exibição: {current_item.display_time}")

            # Calcula offset decorrido do programa que está no ar
            offset = 0
            if current_item.start_dt <= now < current_item.end_dt:
                offset = int((now - current_item.start_dt).total_seconds())
            elif current_item.start_dt < now:
                offset = int((now - current_item.start_dt).total_seconds()) % max(60, current_item.duration_seconds)
            else:
                offset = 0

            self.player_widget.load_media(
                file_path=current_item.file_path,
                title=f"{channel.icon} CH{channel.number:02d} | {current_item.full_display_title}",
                offset_seconds=offset,
                channel_number=channel.number,
                channel_name=channel.name
            )
        else:
            self.lbl_now_title.setText("Nenhuma mídia indexada para este canal")
            self.lbl_now_time_range.setText("")

    def _on_schedule_item_clicked(self, list_item: QListWidgetItem):
        item: ScheduleItem = list_item.data(Qt.UserRole)
        if item:
            self.current_playing_item = item
            self.lbl_now_title.setText(item.full_display_title)
            self.lbl_now_time_range.setText(f"Horário de Exibição: {item.display_time}")
            channel = self.schedule_mgr.channels[self.current_channel_idx]
            self.player_widget.load_media(
                file_path=item.file_path,
                title=f"{channel.icon} CH{channel.number:02d} | {item.full_display_title}",
                offset_seconds=0,
                channel_number=channel.number,
                channel_name=channel.name
            )

    def _play_next_scheduled_item(self):
        if not self.schedule_mgr.channels:
            return

        channel = self.schedule_mgr.channels[self.current_channel_idx]
        if not channel.schedule:
            return

        if self.current_playing_item:
            try:
                curr_idx = channel.schedule.index(self.current_playing_item)
                next_idx = (curr_idx + 1) % len(channel.schedule)
            except ValueError:
                next_idx = 0
        else:
            next_idx = 0

        next_item = channel.schedule[next_idx]
        self.current_playing_item = next_item
        self.lbl_now_title.setText(next_item.full_display_title)
        self.lbl_now_time_range.setText(f"Horário de Exibição: {next_item.display_time}")
        self.player_widget.load_media(
            file_path=next_item.file_path,
            title=f"{channel.icon} CH{channel.number:02d} | {next_item.full_display_title}",
            offset_seconds=0,
            channel_number=channel.number,
            channel_name=channel.name
        )

    def _next_channel(self):
        self._select_channel(self.current_channel_idx + 1)

    def _prev_channel(self):
        self._select_channel(self.current_channel_idx - 1)

    def _update_clock_and_epg(self):
        now = datetime.now()
        self.lbl_clock.setText(now.strftime("%H:%M:%S"))

        # Atualiza a grade se o canal atual expirou E o player não estiver no meio da reprodução ativa
        if self.current_playing_item and self.schedule_mgr.channels:
            is_playing = (self.player_widget.player.playbackState() == QMediaPlayer.PlayingState)
            
            # Se o player terminou ou está parado e o horário do item passou, sintoniza o programa atual no ar
            if not is_playing and now >= self.current_playing_item.end_dt:
                channel = self.schedule_mgr.channels[self.current_channel_idx]
                self._tune_current_program(channel)
                self._populate_schedule_list(channel)

    def closeEvent(self, event):
        self.clock_timer.stop()
        self.player_widget.stop()
        super().closeEvent(event)
