import os
import sys
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox, QFrame,
    QSlider, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QTime
from PySide6.QtGui import QIcon, QFont

from app.core.streamer import TVCastManager, TVDevice, get_local_ip
from app.utils.media_helpers import format_file_size


def format_seconds(seconds: float) -> str:
    """Formata segundos em HH:MM:SS ou MM:SS."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class CastDialog(QDialog):
    """
    Diálogo para descobrir Smart TVs na rede e transmitir vídeos/áudios
    com controle de reprodução remoto em tempo real.
    """

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.manager = TVCastManager.get_instance()
        self.devices_by_id: Dict[str, TVDevice] = {}
        self._user_seeking = False
        self._media_duration = 0.0

        self.setWindowTitle("📡 Transmitir para TV — MediaFinder")
        self.resize(580, 520)
        self.setMinimumSize(500, 440)
        self.setModal(False)  # Permite continuar usando o app enquanto assiste

        self._init_ui()
        self._connect_manager_signals()

        # Inicia a busca automática ao abrir a janela
        self._start_scan()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0F1217;
                color: #FFFFFF;
                font-family: 'Noto Sans', 'Noto Color Emoji', sans-serif;
            }
            QLabel {
                color: #E2E8F0;
            }
            QPushButton {
                background-color: #1E2430;
                color: #FFFFFF;
                border: 1px solid #2D3748;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2D3748;
                border-color: #4A5568;
            }
            QPushButton#primary_btn {
                background-color: #2563EB;
                border-color: #3B82F6;
                font-weight: bold;
            }
            QPushButton#primary_btn:hover {
                background-color: #1D4ED8;
            }
            QPushButton#danger_btn {
                background-color: #DC2626;
                border-color: #EF4444;
            }
            QPushButton#danger_btn:hover {
                background-color: #B91C1C;
            }
            QListWidget {
                background-color: #161A22;
                border: 1px solid #242A35;
                border-radius: 6px;
                color: #F8FAFC;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #1E2430;
            }
            QListWidget::item:selected {
                background-color: #1E3A8A;
                color: #FFFFFF;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2D3748;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38BDF8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. Cabeçalho com dados da mídia
        header_card = QFrame()
        header_card.setStyleSheet("background-color: #161B24; border: 1px solid #252D3D; border-radius: 8px; padding: 4px;")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(10, 8, 10, 8)

        lbl_icon = QLabel("🎬")
        lbl_icon.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(lbl_icon)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        file_name = os.path.basename(self.file_path)
        lbl_file = QLabel(file_name)
        lbl_file.setStyleSheet("font-size: 13px; font-weight: bold; color: #38BDF8;")
        info_layout.addWidget(lbl_file)

        try:
            sz = os.path.getsize(self.file_path)
            sz_str = format_file_size(sz)
        except Exception:
            sz_str = "-"
        lbl_meta = QLabel(f"Tamanho: {sz_str} • IP Local: {get_local_ip()}")
        lbl_meta.setStyleSheet("font-size: 11px; color: #94A3B8;")
        info_layout.addWidget(lbl_meta)
        h_layout.addLayout(info_layout, 1)

        layout.addWidget(header_card)

        # 2. Seção de Descoberta de TVs
        section_layout = QHBoxLayout()
        self.lbl_scan_status = QLabel("🔍 Buscando TVs e dispositivos na rede...")
        self.lbl_scan_status.setStyleSheet("color: #38BDF8; font-weight: 500; font-size: 12px;")
        section_layout.addWidget(self.lbl_scan_status, 1)

        self.btn_refresh = QPushButton("🔄 Atualizar")
        self.btn_refresh.clicked.connect(self._start_scan)
        section_layout.addWidget(self.btn_refresh)

        self.btn_manual_ip = QPushButton("➕ Inserir IP...")
        self.btn_manual_ip.clicked.connect(self._add_manual_ip)
        section_layout.addWidget(self.btn_manual_ip)
        layout.addLayout(section_layout)

        # Lista de Dispositivos
        self.list_devices = QListWidget()
        self.list_devices.itemDoubleClicked.connect(self._on_start_cast)
        layout.addWidget(self.list_devices, 1)

        # Botão Conectar
        self.btn_start_cast = QPushButton("▶ Conectar e Transmitir para a TV")
        self.btn_start_cast.setObjectName("primary_btn")
        self.btn_start_cast.setStyleSheet("padding: 9px; font-size: 13px;")
        self.btn_start_cast.clicked.connect(self._on_start_cast)
        layout.addWidget(self.btn_start_cast)

        # 3. Painel de Controle Remoto Ativo (exibido durante o streaming)
        self.remote_panel = QFrame()
        self.remote_panel.setStyleSheet("""
            QFrame {
                background-color: #131A26;
                border: 1px solid #1E40AF;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        r_layout = QVBoxLayout(self.remote_panel)
        r_layout.setContentsMargins(12, 10, 12, 10)
        r_layout.setSpacing(8)

        # Status da Transmissão
        self.lbl_remote_title = QLabel("🟢 Transmitindo na TV")
        self.lbl_remote_title.setStyleSheet("color: #10B981; font-weight: bold; font-size: 13px;")
        r_layout.addWidget(self.lbl_remote_title)

        # Barra de Progresso / Seek
        seek_layout = QHBoxLayout()
        self.lbl_current_time = QLabel("00:00")
        self.lbl_current_time.setStyleSheet("color: #94A3B8; font-family: monospace; font-size: 11px;")
        seek_layout.addWidget(self.lbl_current_time)

        self.slider_progress = QSlider(Qt.Horizontal)
        self.slider_progress.setRange(0, 1000)
        self.slider_progress.sliderPressed.connect(self._on_seek_pressed)
        self.slider_progress.sliderReleased.connect(self._on_seek_released)
        seek_layout.addWidget(self.slider_progress, 1)

        self.lbl_total_time = QLabel("00:00")
        self.lbl_total_time.setStyleSheet("color: #94A3B8; font-family: monospace; font-size: 11px;")
        seek_layout.addWidget(self.lbl_total_time)
        r_layout.addLayout(seek_layout)

        # Controles (Play/Pause, Parar, Volume)
        ctrl_layout = QHBoxLayout()
        self.btn_play_pause = QPushButton("⏸️ Pausar")
        self.btn_play_pause.clicked.connect(self._toggle_play_pause)
        ctrl_layout.addWidget(self.btn_play_pause)

        self.btn_stop = QPushButton("⏹️ Parar Transmissão")
        self.btn_stop.setObjectName("danger_btn")
        self.btn_stop.clicked.connect(self._stop_cast)
        ctrl_layout.addWidget(self.btn_stop)

        ctrl_layout.addStretch(1)

        lbl_vol = QLabel("🔊")
        ctrl_layout.addWidget(lbl_vol)

        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(85)
        self.slider_volume.setFixedWidth(100)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)
        ctrl_layout.addWidget(self.slider_volume)

        self.btn_mute = QPushButton("🔇")
        self.btn_mute.setFixedSize(32, 28)
        self.btn_mute.clicked.connect(self.manager.toggle_mute)
        ctrl_layout.addWidget(self.btn_mute)

        r_layout.addLayout(ctrl_layout)
        layout.addWidget(self.remote_panel)

        # Esconde o painel remoto inicialmente até iniciar transmissão
        self.remote_panel.setVisible(self.manager.is_casting)

    def _connect_manager_signals(self):
        self.manager.device_found.connect(self._on_device_found)
        self.manager.discovery_finished.connect(self._on_discovery_finished)
        self.manager.cast_started.connect(self._on_cast_started)
        self.manager.cast_stopped.connect(self._on_cast_stopped)
        self.manager.status_updated.connect(self._on_status_updated)
        self.manager.volume_updated.connect(self._on_volume_updated)
        self.manager.error_occurred.connect(self._on_error)

    def _start_scan(self):
        self.lbl_scan_status.setText("🔍 Buscando TVs na rede local (Chromecast / LG webOS)...")
        self.btn_refresh.setEnabled(False)
        self.manager.start_discovery()

        # Já carrega qualquer dispositivo que tenha sido encontrado anteriormente
        for dev in self.manager.discovered_devices.values():
            self._on_device_found(dev)

    def _on_device_found(self, device: TVDevice):
        if device.device_id in self.devices_by_id:
            return

        self.devices_by_id[device.device_id] = device

        icon_char = "📺" if "tv" in device.model.lower() or "lg" in device.name.lower() else "⚡"
        text = f"{icon_char}  {device.name}  —  {device.model} ({device.host})"

        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, device.device_id)
        self.list_devices.addItem(item)

        if self.list_devices.count() == 1:
            self.list_devices.setCurrentRow(0)

    def _on_discovery_finished(self, total: int):
        self.btn_refresh.setEnabled(True)
        if total == 0:
            self.lbl_scan_status.setText("⚠️ Nenhuma TV encontrada. Clique em '➕ Inserir IP' se souber o IP da sua TV.")
        else:
            self.lbl_scan_status.setText(f"✓ {total} dispositivo(s) encontrado(s) na rede.")

    def _add_manual_ip(self):
        ip, ok = QInputDialog.getText(
            self,
            "Adicionar TV por IP",
            "Digite o endereço IP da TV na rede local (Ex: 192.168.0.26):"
        )
        if ok and ip.strip():
            self.lbl_scan_status.setText(f"Tentando conectar ao IP {ip}...")
            self.manager.add_manual_device(ip.strip())

    def _on_start_cast(self):
        current_item = self.list_devices.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Aviso", "Selecione uma TV ou dispositivo na lista.")
            return

        dev_id = current_item.data(Qt.UserRole)
        device = self.devices_by_id.get(dev_id)
        if not device:
            return

        self.lbl_scan_status.setText(f"Conectando a {device.name} e iniciando transmissão...")
        self.btn_start_cast.setEnabled(False)
        self.btn_start_cast.setText("⌛ Conectando...")
        self.manager.cast_media(device, self.file_path)

    def _on_cast_started(self, device_name: str, file_name: str):
        self.btn_start_cast.setEnabled(True)
        self.btn_start_cast.setText("▶ Conectar e Transmitir para a TV")
        self.remote_panel.setVisible(True)
        self.lbl_remote_title.setText(f"🟢 Transmitindo para: {device_name}")
        self.btn_play_pause.setText("⏸️ Pausar")

    def _on_cast_stopped(self):
        self.remote_panel.setVisible(False)
        self.btn_start_cast.setEnabled(True)
        self.lbl_remote_title.setText("Transmissão finalizada.")

    def _toggle_play_pause(self):
        if self.btn_play_pause.text().startswith("⏸️"):
            self.manager.pause()
            self.btn_play_pause.setText("▶️ Continuar")
        else:
            self.manager.play()
            self.btn_play_pause.setText("⏸️ Pausar")

    def _stop_cast(self):
        self.manager.stop_cast()

    def _on_seek_pressed(self):
        self._user_seeking = True

    def _on_seek_released(self):
        self._user_seeking = False
        if self._media_duration > 0:
            val = self.slider_progress.value()
            target_sec = (val / 1000.0) * self._media_duration
            self.manager.seek(target_sec)

    def _on_volume_changed(self, value: int):
        self.manager.set_volume(value / 100.0)

    def _on_status_updated(self, state: str, current_sec: float, duration_sec: float):
        if not self._user_seeking:
            self._media_duration = duration_sec
            if duration_sec > 0:
                pos = int((current_sec / duration_sec) * 1000)
                self.slider_progress.setValue(pos)
                self.lbl_total_time.setText(format_seconds(duration_sec))
            self.lbl_current_time.setText(format_seconds(current_sec))

        if state == "PLAYING":
            self.btn_play_pause.setText("⏸️ Pausar")
        elif state == "PAUSED":
            self.btn_play_pause.setText("▶️ Continuar")

    def _on_volume_updated(self, volume: float, is_muted: bool):
        self.slider_volume.blockSignals(True)
        self.slider_volume.setValue(int(volume * 100))
        self.slider_volume.blockSignals(False)
        self.btn_mute.setText("🔊" if is_muted else "🔇")

    def _on_error(self, message: str):
        self.btn_start_cast.setEnabled(True)
        self.btn_start_cast.setText("▶ Conectar e Transmitir para a TV")
        QMessageBox.critical(self, "Erro na Transmissão", message)
