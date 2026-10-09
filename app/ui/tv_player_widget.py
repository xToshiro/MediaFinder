import os
import sys
import re
from typing import Optional, List, Dict, Any


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QStyle, QFrame, QSizePolicy, QMenu
)
from PySide6.QtCore import Qt, QUrl, Signal, QTime, QTimer, QPropertyAnimation, QEasingCurve, QEvent, QPoint
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData
from PySide6.QtMultimediaWidgets import QVideoWidget

from app.utils.system_ops import open_file


class TVPlayerWidget(QWidget):
    """Widget de player de vídeo integrado com controles de reprodução, seleção de áudio/legenda, tela cheia e OSD estilo TV."""

    playback_finished = Signal()
    fullscreen_requested = Signal(bool)
    duration_resolved = Signal(str, int)  # (file_path, duration_seconds)


    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path: Optional[str] = None
        self._is_seeking = False
        self._is_fullscreen = False
        self._target_offset_ms = 0
        self._seek_applied = False
        self._is_muted = False
        self._last_unmuted_volume = 85

        self._init_player()
        self._init_ui()
        self._init_osd_overlays()

    def _init_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.tracksChanged.connect(self._on_tracks_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        self._skip_timer = QTimer(self)
        self._skip_timer.setSingleShot(True)
        self._skip_timer.timeout.connect(self._on_auto_skip_timeout)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.header_info = QFrame(self)
        self.header_info.setStyleSheet("""
            QFrame {
                background-color: #12151B;
                border: 1px solid #242A34;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        ho_layout = QHBoxLayout(self.header_info)
        ho_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_live_badge = QLabel("🔴 NO AR")
        self.lbl_live_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")
        ho_layout.addWidget(self.lbl_live_badge)

        self.lbl_now_playing = QLabel("Nenhuma mídia em reprodução")
        self.lbl_now_playing.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 12px;")
        ho_layout.addWidget(self.lbl_now_playing, 1)

        layout.addWidget(self.header_info)

        self.video_container = QFrame(self)
        self.video_container.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vid_layout = QVBoxLayout(self.video_container)
        vid_layout.setContentsMargins(0, 0, 0, 0)
        vid_layout.addWidget(self.video_widget)

        layout.addWidget(self.video_container, 1)

        self.controls_bar = QFrame(self)
        self.controls_bar.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #242A34;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        controls_layout = QVBoxLayout(self.controls_bar)
        controls_layout.setContentsMargins(8, 4, 8, 6)
        controls_layout.setSpacing(4)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(8)

        self.lbl_current_time = QLabel("00:00")
        self.lbl_current_time.setStyleSheet("color: #94A3B8; font-size: 11px; font-family: monospace;")
        time_layout.addWidget(self.lbl_current_time)

        self.slider_progress = QSlider(Qt.Horizontal)
        self.slider_progress.setRange(0, 1000)
        self.slider_progress.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 5px;
                background: #2D3748;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #38BDF8);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self.slider_progress.sliderPressed.connect(self._on_slider_pressed)
        self.slider_progress.sliderReleased.connect(self._on_slider_released)
        time_layout.addWidget(self.slider_progress, 1)

        self.lbl_total_time = QLabel("00:00")
        self.lbl_total_time.setStyleSheet("color: #94A3B8; font-size: 11px; font-family: monospace;")
        time_layout.addWidget(self.lbl_total_time)

        controls_layout.addLayout(time_layout)

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(6)

        self.btn_play_pause = QPushButton("▶ Reproduzir")
        self.btn_play_pause.setObjectName("primary_action_btn")
        self.btn_play_pause.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        btns_layout.addWidget(self.btn_play_pause)

        self.btn_stop = QPushButton("⏹ Parar")
        self.btn_stop.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        self.btn_stop.clicked.connect(self.stop)
        btns_layout.addWidget(self.btn_stop)

        self.btn_audio_track = QPushButton("🎧 Áudio (A)")
        self.btn_audio_track.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        self.btn_audio_track.setToolTip("Alternar faixa de áudio / Dual Áudio (Tecla A). Clique com botão direito para ver opções.")
        self.btn_audio_track.clicked.connect(self.cycle_audio_track)
        self.btn_audio_track.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_audio_track.customContextMenuRequested.connect(self.show_audio_menu)
        btns_layout.addWidget(self.btn_audio_track)

        self.btn_subtitle_track = QPushButton("💬 Legenda (S)")
        self.btn_subtitle_track.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        self.btn_subtitle_track.setToolTip("Alternar legendas (Tecla S). Clique com botão direito para ver opções.")
        self.btn_subtitle_track.clicked.connect(self.cycle_subtitle_track)
        self.btn_subtitle_track.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_subtitle_track.customContextMenuRequested.connect(self.show_subtitle_menu)
        btns_layout.addWidget(self.btn_subtitle_track)

        self.btn_mute_toggle = QPushButton("🔊")
        self.btn_mute_toggle.setStyleSheet("font-size: 13px; padding: 4px 6px; background: transparent; border: none;")
        self.btn_mute_toggle.setToolTip("Silenciar / Ativar Som (M)")
        self.btn_mute_toggle.clicked.connect(self.toggle_mute)
        btns_layout.addWidget(self.btn_mute_toggle)

        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(85)
        self.slider_volume.setMaximumWidth(80)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)
        btns_layout.addWidget(self.slider_volume)

        btns_layout.addStretch()

        ext_label = "🚀 Abrir no Windows Player" if sys.platform == "win32" else "🚀 Abrir no Reprodutor Padrão"
        self.btn_external_player = QPushButton(ext_label)
        self.btn_external_player.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        ext_tip = "Abre o arquivo atual no player padrão do Windows (VLC, etc.)" if sys.platform == "win32" else "Abre o arquivo atual no player de vídeo padrão do Linux (VLC, Haruna, etc.)"
        self.btn_external_player.setToolTip(ext_tip)
        self.btn_external_player.clicked.connect(self._open_in_external_player)
        btns_layout.addWidget(self.btn_external_player)


        self.btn_fullscreen = QPushButton("⛶ Tela Cheia")
        self.btn_fullscreen.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        btns_layout.addWidget(self.btn_fullscreen)

        controls_layout.addLayout(btns_layout)
        layout.addWidget(self.controls_bar)

    def _init_osd_overlays(self):
        """Inicializa janelas de OSD flutuantes de alta prioridade (sobrepondo o DirectX do QVideoWidget)."""
        popup_flags = Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint

        # 1. Overlay de Transição / Sintonização de Canal (Cobre todo o quadro durante a troca)
        self.osd_transition = QFrame(None, popup_flags)
        self.osd_transition.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.osd_transition.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.osd_transition.setAttribute(Qt.WA_TranslucentBackground, True)
        self.osd_transition.setStyleSheet("""
            QFrame {
                background-color: rgba(6, 9, 15, 0.96);
                border: 1px solid #1E293B;
                border-radius: 8px;
            }
        """)
        trans_layout = QVBoxLayout(self.osd_transition)
        trans_layout.setAlignment(Qt.AlignCenter)
        
        self.lbl_trans_text = QLabel("📡 SINTONIZANDO...")
        self.lbl_trans_text.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 18px;
            font-weight: 900;
            color: #22C55E;
            letter-spacing: 3px;
        """)
        self.lbl_trans_text.setAlignment(Qt.AlignCenter)
        trans_layout.addWidget(self.lbl_trans_text)

        self.anim_trans_fade = QPropertyAnimation(self.osd_transition, b"windowOpacity")
        self.anim_trans_fade.setDuration(260)
        self.anim_trans_fade.setEasingCurve(QEasingCurve.OutCubic)

        # 2. Overlay de Troca de Canal (Top-Right)
        self.osd_channel = QFrame(None, popup_flags)
        self.osd_channel.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.osd_channel.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.osd_channel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.osd_channel.setStyleSheet("""
            QFrame {
                background-color: rgba(12, 17, 26, 0.93);
                border: 2px solid #22C55E;
                border-radius: 8px;
                padding: 8px 14px;
            }
        """)
        osd_ch_layout = QVBoxLayout(self.osd_channel)
        osd_ch_layout.setContentsMargins(10, 8, 10, 8)
        osd_ch_layout.setSpacing(3)

        self.lbl_osd_channel_num = QLabel("CH 01")
        self.lbl_osd_channel_num.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 22px;
            font-weight: 900;
            color: #22C55E;
            letter-spacing: 2px;
        """)
        osd_ch_layout.addWidget(self.lbl_osd_channel_num)

        self.lbl_osd_channel_title = QLabel("CANAL PRINCIPAL")
        self.lbl_osd_channel_title.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #F8FAFC;
        """)
        osd_ch_layout.addWidget(self.lbl_osd_channel_title)

        self.lbl_osd_program_title = QLabel("Programa em Exibição")
        self.lbl_osd_program_title.setStyleSheet("""
            font-size: 11px;
            color: #38BDF8;
        """)
        osd_ch_layout.addWidget(self.lbl_osd_program_title)

        self.anim_channel_fade = QPropertyAnimation(self.osd_channel, b"windowOpacity")
        self.anim_channel_fade.setDuration(220)
        self.anim_channel_fade.setEasingCurve(QEasingCurve.OutCubic)

        self.timer_channel_osd = QTimer(self)
        self.timer_channel_osd.setSingleShot(True)
        self.timer_channel_osd.timeout.connect(self._fade_out_channel_osd)

        # 3. Overlay de Volume Estilo TV Antiga (Segmented Green Bars OSD)
        self.osd_volume = QFrame(None, popup_flags)
        self.osd_volume.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.osd_volume.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.osd_volume.setAttribute(Qt.WA_TranslucentBackground, True)
        self.osd_volume.setStyleSheet("""
            QFrame {
                background-color: rgba(12, 17, 26, 0.93);
                border: 2px solid #10B981;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        osd_vol_layout = QVBoxLayout(self.osd_volume)
        osd_vol_layout.setContentsMargins(10, 6, 10, 6)
        osd_vol_layout.setSpacing(2)

        self.lbl_osd_vol_header = QLabel("VOLUME")
        self.lbl_osd_vol_header.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            font-weight: 900;
            color: #10B981;
            letter-spacing: 2px;
        """)
        osd_vol_layout.addWidget(self.lbl_osd_vol_header)

        self.lbl_osd_vol_bars = QLabel("▮▮▮▮▮▮▮▮▯▯▯▯▯▯ 50%")
        self.lbl_osd_vol_bars.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
            letter-spacing: 1px;
        """)
        osd_vol_layout.addWidget(self.lbl_osd_vol_bars)

        self.anim_volume_fade = QPropertyAnimation(self.osd_volume, b"windowOpacity")
        self.anim_volume_fade.setDuration(180)
        self.anim_volume_fade.setEasingCurve(QEasingCurve.OutCubic)

        self.timer_volume_osd = QTimer(self)
        self.timer_volume_osd.setSingleShot(True)
        self.timer_volume_osd.timeout.connect(self._fade_out_volume_osd)

        # 4. Overlay de Informações de Áudio / Legenda (Top-Left)
        self.osd_track = QFrame(None, popup_flags)
        self.osd_track.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.osd_track.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.osd_track.setAttribute(Qt.WA_TranslucentBackground, True)
        self.osd_track.setStyleSheet("""
            QFrame {
                background-color: rgba(12, 17, 26, 0.93);
                border: 2px solid #38BDF8;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        track_layout = QVBoxLayout(self.osd_track)
        track_layout.setContentsMargins(10, 6, 10, 6)
        track_layout.setSpacing(2)

        self.lbl_osd_track_type = QLabel("🎧 ÁUDIO")
        self.lbl_osd_track_type.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            font-weight: 900;
            color: #38BDF8;
            letter-spacing: 2px;
        """)
        track_layout.addWidget(self.lbl_osd_track_type)

        self.lbl_osd_track_info = QLabel("[1/2] Português")
        self.lbl_osd_track_info.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #FFFFFF;
        """)
        track_layout.addWidget(self.lbl_osd_track_info)

        self.anim_track_fade = QPropertyAnimation(self.osd_track, b"windowOpacity")
        self.anim_track_fade.setDuration(180)
        self.anim_track_fade.setEasingCurve(QEasingCurve.OutCubic)

        self.timer_track_osd = QTimer(self)
        self.timer_track_osd.setSingleShot(True)
        self.timer_track_osd.timeout.connect(self._fade_out_track_osd)

    def showEvent(self, event):
        super().showEvent(event)
        win = self.window()
        if win and win != self:
            win.installEventFilter(self)

    def hideEvent(self, event):
        self.hide_osds()
        super().hideEvent(event)

    def hide_osds(self):
        if hasattr(self, 'osd_transition'):
            self.osd_transition.hide()
        if hasattr(self, 'osd_channel'):
            self.osd_channel.hide()
        if hasattr(self, 'osd_volume'):
            self.osd_volume.hide()
        if hasattr(self, 'osd_track'):
            self.osd_track.hide()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Move, QEvent.Resize, QEvent.WindowStateChange):
            self._reposition_osd_overlays()
        elif event.type() in (QEvent.Hide, QEvent.Close):
            self.hide_osds()
        return super().eventFilter(watched, event)

    def _reposition_osd_overlays(self):
        """Ajusta o posicionamento responsivo dos OSDs em coordenadas globais da tela."""
        if not self.isVisible() or not self.video_widget.isVisible():
            return

        try:
            top_left = self.video_widget.mapToGlobal(QPoint(0, 0))
        except Exception:
            return

        w = self.video_widget.width()
        h = self.video_widget.height()

        if w <= 10 or h <= 10:
            return

        # OSD de Transição: Cobre todo o quadro de vídeo
        if self.osd_transition.isVisible():
            self.osd_transition.setGeometry(top_left.x(), top_left.y(), w, h)

        # OSD de Canal: Canto Superior Direito com margem de 20px
        ch_w = min(360, max(260, int(w * 0.45)))
        self.osd_channel.setFixedWidth(ch_w)
        self.osd_channel.adjustSize()
        ch_x = top_left.x() + max(10, w - self.osd_channel.width() - 20)
        ch_y = top_left.y() + 20
        self.osd_channel.move(ch_x, ch_y)

        # OSD de Volume: Canto Inferior Esquerdo com margem de 24px
        vol_w = min(320, max(220, int(w * 0.38)))
        self.osd_volume.setFixedWidth(vol_w)
        self.osd_volume.adjustSize()
        vol_x = top_left.x() + 24
        vol_y = top_left.y() + max(10, h - self.osd_volume.height() - 24)
        self.osd_volume.move(vol_x, vol_y)

        # OSD de Faixa de Áudio / Legenda: Canto Superior Esquerdo com margem de 20px
        track_w = min(340, max(240, int(w * 0.40)))
        self.osd_track.setFixedWidth(track_w)
        self.osd_track.adjustSize()
        self.osd_track.move(top_left.x() + 20, top_left.y() + 20)

    def trigger_channel_transition(self, channel_number: int, channel_name: str):
        """Dispara a animação de transição suave de canal (TV tuner switch curtain)."""
        if not self.isVisible() or not self.video_widget.isVisible():
            return

        try:
            top_left = self.video_widget.mapToGlobal(QPoint(0, 0))
            w = self.video_widget.width()
            h = self.video_widget.height()
            if w > 10 and h > 10:
                self.osd_transition.setGeometry(top_left.x(), top_left.y(), w, h)
        except Exception:
            pass

        self.lbl_trans_text.setText(f"📡 SINTONIZANDO CH {channel_number:02d}...")
        self.osd_transition.setWindowOpacity(1.0)
        self.osd_transition.show()
        self.osd_transition.raise_()

        QTimer.singleShot(140, self._fade_out_transition_osd)

    def _fade_out_transition_osd(self):
        self.anim_trans_fade.stop()
        self.anim_trans_fade.setStartValue(self.osd_transition.windowOpacity())
        self.anim_trans_fade.setEndValue(0.0)
        self.anim_trans_fade.finished.connect(self._on_transition_finished)
        self.anim_trans_fade.start()

    def _on_transition_finished(self):
        try:
            self.anim_trans_fade.finished.disconnect(self._on_transition_finished)
        except Exception:
            pass
        self.osd_transition.hide()

    def show_channel_osd(self, channel_number: int, channel_name: str, program_title: str = ""):
        """Exibe o banner OSD animado de mudança de canal."""
        self.lbl_osd_channel_num.setText(f"CH {channel_number:02d}")
        self.lbl_osd_channel_title.setText(channel_name.upper())
        self.lbl_osd_program_title.setText(program_title or "Transmissão Contínua")

        self.osd_channel.adjustSize()
        self._reposition_osd_overlays()
        
        self.osd_channel.show()
        self.osd_channel.raise_()

        self.anim_channel_fade.stop()
        self.anim_channel_fade.setStartValue(self.osd_channel.windowOpacity())
        self.anim_channel_fade.setEndValue(1.0)
        self.anim_channel_fade.start()

        self.timer_channel_osd.stop()
        self.timer_channel_osd.start(2800)

    def _fade_out_channel_osd(self):
        self.anim_channel_fade.stop()
        self.anim_channel_fade.setStartValue(self.osd_channel.windowOpacity())
        self.anim_channel_fade.setEndValue(0.0)
        self.anim_channel_fade.start()

    def show_volume_osd(self, volume_percent: int, is_muted: bool = False):
        """Exibe o OSD com barras clássicas de volume no estilo das televisões vintage."""
        total_blocks = 14
        vol = max(0, min(100, volume_percent))

        if is_muted or vol == 0:
            self.lbl_osd_vol_header.setText("VOLUME: SILENCIADO")
            self.lbl_osd_vol_header.setStyleSheet("font-family: monospace; font-size: 12px; font-weight: 900; color: #EF4444; letter-spacing: 2px;")
            self.lbl_osd_vol_bars.setText("<span style='color: #EF4444; font-weight: bold;'>🔇 MUTE (0%)</span>")
        else:
            filled_count = int(round((vol / 100.0) * total_blocks))
            empty_count = total_blocks - filled_count

            filled_str = "▮" * filled_count
            empty_str = "▯" * empty_count
            
            html_text = (
                f"<span style='color: #22C55E; font-weight: bold;'>{filled_str}</span>"
                f"<span style='color: #475569;'>{empty_str}</span> "
                f"<span style='color: #10B981; font-weight: 900;'>{vol}%</span>"
            )
            self.lbl_osd_vol_header.setText("VOLUME")
            self.lbl_osd_vol_header.setStyleSheet("font-family: monospace; font-size: 12px; font-weight: 900; color: #10B981; letter-spacing: 2px;")
            self.lbl_osd_vol_bars.setText(html_text)

        self.osd_volume.adjustSize()
        self._reposition_osd_overlays()
        
        self.osd_volume.show()
        self.osd_volume.raise_()

        self.anim_volume_fade.stop()
        self.anim_volume_fade.setStartValue(self.osd_volume.windowOpacity())
        self.anim_volume_fade.setEndValue(1.0)
        self.anim_volume_fade.start()

        self.timer_volume_osd.stop()
        self.timer_volume_osd.start(1800)

    def _fade_out_volume_osd(self):
        self.anim_volume_fade.stop()
        self.anim_volume_fade.setStartValue(self.osd_volume.windowOpacity())
        self.anim_volume_fade.setEndValue(0.0)
        self.anim_volume_fade.start()

    def show_track_osd(self, track_type: str, message: str):
        """Exibe o OSD com a indicação de troca de Faixa de Áudio ou Legenda."""
        self.lbl_osd_track_type.setText(track_type)
        self.lbl_osd_track_info.setText(message)

        self.osd_track.adjustSize()
        self._reposition_osd_overlays()
        
        self.osd_track.show()
        self.osd_track.raise_()

        self.anim_track_fade.stop()
        self.anim_track_fade.setStartValue(self.osd_track.windowOpacity())
        self.anim_track_fade.setEndValue(1.0)
        self.anim_track_fade.start()

        self.timer_track_osd.stop()
        self.timer_track_osd.start(2400)

    def _fade_out_track_osd(self):
        self.anim_track_fade.stop()
        self.anim_track_fade.setStartValue(self.osd_track.windowOpacity())
        self.anim_track_fade.setEndValue(0.0)
        self.anim_track_fade.start()

    def _format_track_title(self, meta: QMediaMetaData, idx: int, default_type: str = "Faixa") -> str:
        lang = meta.stringValue(QMediaMetaData.Key.Language) if hasattr(meta, 'stringValue') else ""
        title = meta.stringValue(QMediaMetaData.Key.Title) if hasattr(meta, 'stringValue') else ""
        if not title and hasattr(meta, 'stringValue'):
            title = meta.stringValue(QMediaMetaData.Key.Description) or ""

        if lang and title:
            return f"{title} [{lang.upper()}]"
        elif lang:
            return f"Idioma: {lang.upper()}"
        elif title:
            return title
        return f"{default_type} #{idx + 1}"

    def cycle_audio_track(self):
        """Alterna ciclicamente entre as faixas de áudio disponíveis (Dual Áudio / Idiomas)."""
        tracks = self.player.audioTracks()
        if not tracks:
            self.show_track_osd("🎧 ÁUDIO", "Faixa Única / Padrão")
            return

        if len(tracks) == 1:
            title = self._format_track_title(tracks[0], 0, "Áudio")
            self.show_track_osd("🎧 ÁUDIO", f"[1/1] {title}")
            return

        curr = self.player.activeAudioTrack()
        next_idx = (curr + 1) % len(tracks)
        self.player.setActiveAudioTrack(next_idx)
        title = self._format_track_title(tracks[next_idx], next_idx, "Áudio")
        self.show_track_osd("🎧 ÁUDIO", f"[{next_idx + 1}/{len(tracks)}] {title}")

    def set_audio_track(self, idx: int):
        """Define diretamente a faixa de áudio ativa pelo índice."""
        tracks = self.player.audioTracks()
        if 0 <= idx < len(tracks):
            self.player.setActiveAudioTrack(idx)
            title = self._format_track_title(tracks[idx], idx, "Áudio")
            self.show_track_osd("🎧 ÁUDIO", f"[{idx + 1}/{len(tracks)}] {title}")

    def show_audio_menu(self):
        """Exibe o menu suspenso de seleção de faixas de áudio."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161A21;
                border: 1px solid #242A34;
                color: #FFFFFF;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563EB;
            }
        """)
        tracks = self.player.audioTracks()
        if not tracks:
            action = menu.addAction("Áudio Padrão (Único)")
            action.setEnabled(False)
        else:
            curr = self.player.activeAudioTrack()
            for idx, meta in enumerate(tracks):
                title = self._format_track_title(meta, idx, "Áudio")
                prefix = "✓ " if idx == curr else "   "
                action = menu.addAction(f"{prefix}[Faixa {idx + 1}] {title}")
                action.triggered.connect(lambda _, i=idx: self.set_audio_track(i))

        menu.exec(self.btn_audio_track.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def cycle_subtitle_track(self):
        """Alterna ciclicamente entre as legendas disponíveis ou desativa."""
        tracks = self.player.subtitleTracks()
        if not tracks:
            self.show_track_osd("💬 LEGENDA", "Nenhuma legenda disponível")
            return

        curr = self.player.activeSubtitleTrack()
        # Se estava desativada (-1), ativa a primeira (0)
        if curr == -1:
            next_idx = 0
            self.player.setActiveSubtitleTrack(next_idx)
            title = self._format_track_title(tracks[next_idx], next_idx, "Legenda")
            self.show_track_osd("💬 LEGENDA", f"[{next_idx + 1}/{len(tracks)}] {title}")
        elif curr < len(tracks) - 1:
            next_idx = curr + 1
            self.player.setActiveSubtitleTrack(next_idx)
            title = self._format_track_title(tracks[next_idx], next_idx, "Legenda")
            self.show_track_osd("💬 LEGENDA", f"[{next_idx + 1}/{len(tracks)}] {title}")
        else:
            self.player.setActiveSubtitleTrack(-1)
            self.show_track_osd("💬 LEGENDA", "DESATIVADA (OFF)")

    def set_subtitle_track(self, idx: int):
        """Define diretamente a faixa de legenda ativa (-1 para desativar)."""
        tracks = self.player.subtitleTracks()
        if idx == -1:
            self.player.setActiveSubtitleTrack(-1)
            self.show_track_osd("💬 LEGENDA", "DESATIVADA (OFF)")
        elif 0 <= idx < len(tracks):
            self.player.setActiveSubtitleTrack(idx)
            title = self._format_track_title(tracks[idx], idx, "Legenda")
            self.show_track_osd("💬 LEGENDA", f"[{idx + 1}/{len(tracks)}] {title}")

    def show_subtitle_menu(self):
        """Exibe o menu suspenso de seleção de legendas."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161A21;
                border: 1px solid #242A34;
                color: #FFFFFF;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563EB;
            }
        """)
        tracks = self.player.subtitleTracks()
        curr = self.player.activeSubtitleTrack()

        # Opção Desativar Legenda
        off_prefix = "✓ " if curr == -1 else "   "
        act_off = menu.addAction(f"{off_prefix}Desativar Legendas (OFF)")
        act_off.triggered.connect(lambda: self.set_subtitle_track(-1))
        menu.addSeparator()

        if not tracks:
            act_none = menu.addAction("Nenhuma legenda embutida")
            act_none.setEnabled(False)
        else:
            for idx, meta in enumerate(tracks):
                title = self._format_track_title(meta, idx, "Legenda")
                prefix = "✓ " if idx == curr else "   "
                action = menu.addAction(f"{prefix}[Legenda {idx + 1}] {title}")
                action.triggered.connect(lambda _, i=idx: self.set_subtitle_track(i))

        menu.exec(self.btn_subtitle_track.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def _on_tracks_changed(self):
        """Atualiza estado dos botões ao detectar faixas no stream de mídia."""
        audio_count = len(self.player.audioTracks())
        sub_count = len(self.player.subtitleTracks())

        if audio_count > 1:
            self.btn_audio_track.setText(f"🎧 Áudio ({audio_count})")
        else:
            self.btn_audio_track.setText("🎧 Áudio (A)")

        if sub_count > 0:
            self.btn_subtitle_track.setText(f"💬 Legenda ({sub_count})")
        else:
            self.btn_subtitle_track.setText("💬 Legenda (S)")

    def set_volume_relative(self, delta_percent: int):
        """Aumenta ou diminui o volume em passos relativos (ex: +5, -5)."""
        curr = self.slider_volume.value()
        new_vol = max(0, min(100, curr + delta_percent))
        if self._is_muted and delta_percent > 0:
            self._is_muted = False
            self.btn_mute_toggle.setText("🔊")
        self.slider_volume.setValue(new_vol)

    def toggle_mute(self):
        """Alterna entre mudo e o último volume configurado."""
        if self._is_muted:
            self._is_muted = False
            self.btn_mute_toggle.setText("🔊")
            self.slider_volume.setValue(self._last_unmuted_volume or 50)
            self.show_volume_osd(self.slider_volume.value(), is_muted=False)
        else:
            if self.slider_volume.value() > 0:
                self._last_unmuted_volume = self.slider_volume.value()
            self._is_muted = True
            self.btn_mute_toggle.setText("🔇")
            self.audio_output.setVolume(0.0)
            self.show_volume_osd(0, is_muted=True)

    def _trigger_auto_skip(self, delay_ms: int = 1500):
        """Dispara um avanço automático com delay para o próximo programa da grade."""
        if not self._skip_timer.isActive():
            self._skip_timer.start(delay_ms)

    def _on_auto_skip_timeout(self):
        self.playback_finished.emit()

    def _on_player_error(self, error, error_string: str = ""):
        """Trata erros nativos de decodificação/codec do QMediaPlayer."""
        if error != QMediaPlayer.Error.NoError:
            self.show_track_osd("⚠️ CODEC NÃO SUPORTADO", "Avançando para o próximo programa...")
            self._trigger_auto_skip(1500)

    def load_media(self, file_path: str, title: str = "", offset_seconds: int = 0, channel_number: Optional[int] = None, channel_name: str = "") -> None:
        """Carrega e inicia a reprodução do arquivo de vídeo ou áudio no ponto exato ao vivo."""
        self._skip_timer.stop()
        self.player.stop()

        self.current_file_path = file_path
        self.lbl_now_playing.setText(title or os.path.basename(file_path))
        self._target_offset_ms = max(0, int(offset_seconds * 1000))
        self._seek_applied = False

        if not os.path.isfile(file_path):
            self.show_track_osd("⚠️ ARQUIVO INACESSÍVEL", "Avançando para o próximo programa...")
            self._trigger_auto_skip(1200)
            return

        if channel_number is not None:
            self.trigger_channel_transition(channel_number, channel_name or title)
            QTimer.singleShot(50, lambda: self.show_channel_osd(channel_number, channel_name or title, title))

        url = QUrl.fromLocalFile(file_path)
        self.player.setSource(url)
        self.player.play()

    def _safe_seek(self, target_ms: int):
        """Executa o seek de forma segura quando os streams estão decodificando."""
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.setPosition(target_ms)

    def toggle_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self._skip_timer.stop()
        self._target_offset_ms = 0
        self._seek_applied = True
        self.player.stop()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play_pause.setText("⏸ Pausar")
        else:
            self.btn_play_pause.setText("▶ Reproduzir")

        if state == QMediaPlayer.StoppedState and self.player.duration() > 0:
            if self.player.position() >= self.player.duration() - 1000:
                self.playback_finished.emit()

    def _on_duration_changed(self, duration_ms: int):
        self.slider_progress.setRange(0, max(1, duration_ms))
        self.lbl_total_time.setText(self._format_time(duration_ms))
        if duration_ms > 0 and self.current_file_path:
            self.duration_resolved.emit(self.current_file_path, int(duration_ms / 1000))


    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playback_finished.emit()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.show_track_osd("⚠️ FORMATO INCOMPATÍVEL", "Avançando para o próximo programa...")
            self._trigger_auto_skip(1500)

    def _on_position_changed(self, position_ms: int):
        if not self._is_seeking:
            self.slider_progress.setValue(position_ms)
        self.lbl_current_time.setText(self._format_time(position_ms))

        # Se houver um offset ao vivo pendente e o primeiro bloco de vídeo começou a tocar
        if self._target_offset_ms > 0 and not self._seek_applied and position_ms > 40:
            duration_ms = self.player.duration()
            if duration_ms > 3000:
                self._seek_applied = True
                target_pos = self._target_offset_ms % duration_ms
                if target_pos > duration_ms - 4000:
                    target_pos = max(1000, duration_ms - 8000)
                elif target_pos < 1000:
                    target_pos = 2000

                self._target_offset_ms = 0
                QTimer.singleShot(100, lambda pos=target_pos: self._safe_seek(pos))
        if not self._is_seeking:
            self.slider_progress.setValue(position_ms)
        self.lbl_current_time.setText(self._format_time(position_ms))

    def _on_slider_pressed(self):
        self._is_seeking = True

    def _on_slider_released(self):
        self._is_seeking = False
        self.player.setPosition(self.slider_progress.value())

    def _on_volume_changed(self, val: int):
        if val > 0 and self._is_muted:
            self._is_muted = False
            self.btn_mute_toggle.setText("🔊")
        self.audio_output.setVolume(val / 100.0)
        self.show_volume_osd(val, is_muted=self._is_muted)

    def _open_in_external_player(self):
        if self.current_file_path:
            self.player.pause()
            open_file(self.current_file_path)

    def toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        self.fullscreen_requested.emit(self._is_fullscreen)

    def _format_time(self, ms: int) -> str:
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000) % 60
        hours = (ms // 3600000)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
