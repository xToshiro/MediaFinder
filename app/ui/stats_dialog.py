import os
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from app.core.database import MediaDatabase
from app.utils.media_helpers import format_file_size
from app.utils.system_ops import open_file, reveal_in_explorer


def format_duration_readable(seconds: int) -> str:
    """Formata segundos em uma string amigável (ex: '38d 14h 22m' ou '2h 45m')."""
    if seconds <= 0:
        return "0 min"
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return " ".join(parts)


class StatsDialog(QDialog):
    """Painel visual de estatísticas, métricas e distribuição da biblioteca de mídias."""

    CATEGORY_COLORS = {
        "video": "#38BDF8",     # Ciano / Azul claro
        "audio": "#34D399",     # Verde esmeralda
        "image": "#FBBF24",     # Âmbar / Amarelo
        "document": "#A78BFA",  # Roxo suave
        "other": "#94A3B8"      # Cinza ardósia
    }

    CATEGORY_NAMES = {
        "video": "🎬 Vídeos",
        "audio": "🎵 Áudios & Músicas",
        "image": "🖼️ Imagens & Fotos",
        "document": "📄 Documentos",
        "other": "📦 Outros"
    }

    def __init__(self, db: MediaDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("📊 Estatísticas da Biblioteca — MediaFinder")
        self.resize(780, 640)
        self.setMinimumSize(680, 520)
        self.setModal(True)

        self._init_ui()
        self._load_stats()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Cabeçalho
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        lbl_title = QLabel("📊 Panorama Geral da sua Biblioteca de Mídias")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch(1)

        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self._load_stats)
        header_layout.addWidget(btn_refresh)

        main_layout.addLayout(header_layout)

        # Scroll Area principal
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 8, 0)
        self.content_layout.setSpacing(16)

        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll, 1)

        # Botão Fechar
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)
        btn_close = QPushButton("Fechar")
        btn_close.setObjectName("primary_action_btn")
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)
        main_layout.addLayout(bottom_layout)

    def _load_stats(self):
        """Carrega e renderiza todas as métricas agregadas."""
        # Limpa conteúdo anterior
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = self.db.get_detailed_stats()
        total_files = stats.get("total_files", 0)
        total_size = stats.get("total_size", 0)
        total_duration = stats.get("total_duration", 0)
        total_drives = stats.get("total_drives", 0)

        # 1. Cards KPI Superiores
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)

        card_files = self._create_kpi_card("📁 Total de Mídias", f"{total_files:,}", "arquivos catalogados", "#38BDF8")
        card_size = self._create_kpi_card("💾 Espaço Ocupado", format_file_size(total_size), "em todos os discos", "#34D399")
        card_dur = self._create_kpi_card("⏱️ Tempo de Reprodução", format_duration_readable(total_duration), "conteúdo contínuo", "#FBBF24")
        card_drives = self._create_kpi_card("💽 Volumes Monitorados", f"{total_drives} Drive(s)", "discos ativos", "#A78BFA")

        cards_grid.addWidget(card_files, 0, 0)
        cards_grid.addWidget(card_size, 0, 1)
        cards_grid.addWidget(card_dur, 0, 2)
        cards_grid.addWidget(card_drives, 0, 3)
        self.content_layout.addLayout(cards_grid)

        # 2. Seção: Distribuição por Categoria
        cat_section = self._create_section_container("📂 Distribuição por Categoria")
        cat_layout = QVBoxLayout(cat_section)
        cat_layout.setContentsMargins(14, 14, 14, 14)
        cat_layout.setSpacing(10)

        categories = stats.get("categories", [])
        for cat_data in categories:
            cat_name = cat_data.get("category", "other")
            count = cat_data.get("count", 0)
            size = cat_data.get("total_size", 0)
            duration = cat_data.get("total_duration", 0)

            pct_size = (size / total_size * 100) if total_size > 0 else 0
            color = self.CATEGORY_COLORS.get(cat_name, "#94A3B8")
            display_name = self.CATEGORY_NAMES.get(cat_name, cat_name.title())

            row = self._create_progress_row(
                title=display_name,
                primary_info=f"{count:,} itens ({format_file_size(size)} — {pct_size:.1f}%)",
                secondary_info=f"⏱️ {format_duration_readable(duration)}" if duration > 0 else "",
                percentage=pct_size,
                color=color
            )
            cat_layout.addWidget(row)

        self.content_layout.addWidget(cat_section)

        # 3. Seção: Armazenamento por Disco/Volume
        drives_section = self._create_section_container("💽 Armazenamento por Disco")
        drives_layout = QVBoxLayout(drives_section)
        drives_layout.setContentsMargins(14, 14, 14, 14)
        drives_layout.setSpacing(10)

        drives = stats.get("drives", [])
        for drv_data in drives:
            drive_letter = drv_data.get("drive", "")
            count = drv_data.get("count", 0)
            size = drv_data.get("total_size", 0)
            pct_size = (size / total_size * 100) if total_size > 0 else 0

            row = self._create_progress_row(
                title=f"Unidade {drive_letter}",
                primary_info=f"{format_file_size(size)} ({count:,} arquivos)",
                secondary_info=f"{pct_size:.1f}% do catálogo",
                percentage=pct_size,
                color="#60A5FA"
            )
            drives_layout.addWidget(row)

        self.content_layout.addWidget(drives_section)

        # 4. Grid Inferior: Top Extensões & Maiores Arquivos
        bottom_grid = QGridLayout()
        bottom_grid.setSpacing(12)

        # Top Extensões
        ext_section = self._create_section_container("🏷️ Principais Formatos")
        ext_layout = QVBoxLayout(ext_section)
        ext_layout.setContentsMargins(12, 12, 12, 12)
        ext_layout.setSpacing(6)

        top_exts = stats.get("top_extensions", [])
        for ext_data in top_exts:
            ext_name = ext_data.get("extension", "")
            count = ext_data.get("count", 0)
            size = ext_data.get("total_size", 0)

            ext_row = QHBoxLayout()
            lbl_ext = QLabel(ext_name.upper())
            lbl_ext.setStyleSheet("""
                background-color: #242A34;
                color: #38BDF8;
                padding: 2px 6px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            """)
            lbl_ext_info = QLabel(f"{count:,} arquivos ({format_file_size(size)})")
            lbl_ext_info.setStyleSheet("color: #94A3B8; font-size: 11px;")
            ext_row.addWidget(lbl_ext)
            ext_row.addWidget(lbl_ext_info)
            ext_row.addStretch(1)
            ext_layout.addLayout(ext_row)

        bottom_grid.addWidget(ext_section, 0, 0)

        # Top 5 Maiores Arquivos
        top_files_section = self._create_section_container("🐘 Maiores Arquivos da Biblioteca")
        top_files_layout = QVBoxLayout(top_files_section)
        top_files_layout.setContentsMargins(12, 12, 12, 12)
        top_files_layout.setSpacing(8)

        largest_files = stats.get("largest_files", [])
        for f in largest_files:
            file_row = self._create_large_file_row(f)
            top_files_layout.addWidget(file_row)

        bottom_grid.addWidget(top_files_section, 0, 1)
        self.content_layout.addLayout(bottom_grid)

    def _create_kpi_card(self, title: str, value: str, subtitle: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #161A21;
                border: 1px solid #242A34;
                border-top: 3px solid {accent_color};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")

        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet("color: #64748B; font-size: 10px;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        layout.addWidget(lbl_sub)

        return card

    def _create_section_container(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #242A34;
                border-radius: 6px;
            }
        """)
        return frame

    def _create_progress_row(self, title: str, primary_info: str, secondary_info: str, percentage: float, color: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        info_layout = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px;")

        lbl_primary = QLabel(primary_info)
        lbl_primary.setStyleSheet("color: #94A3B8; font-size: 11px;")

        info_layout.addWidget(lbl_title)
        info_layout.addWidget(lbl_primary)
        info_layout.addStretch(1)

        if secondary_info:
            lbl_sec = QLabel(secondary_info)
            lbl_sec.setStyleSheet("color: #64748B; font-size: 11px;")
            info_layout.addWidget(lbl_sec)

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(percentage))
        pbar.setTextVisible(False)
        pbar.setFixedHeight(8)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0E1014;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

        layout.addLayout(info_layout)
        layout.addWidget(pbar)

        return widget

    def _create_large_file_row(self, file_data: Dict[str, Any]) -> QFrame:
        row_frame = QFrame()
        row_frame.setStyleSheet("""
            QFrame {
                background-color: #0E1014;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout = QHBoxLayout(row_frame)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        name = file_data.get("name", "")
        size_str = format_file_size(file_data.get("size", 0))
        path = file_data.get("path", "")

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("color: #E2E8F0; font-size: 11px; font-weight: 500;")
        lbl_name.setToolTip(path)

        lbl_size = QLabel(size_str)
        lbl_size.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px;")

        btn_play = QPushButton("▶")
        btn_play.setToolTip("Abrir no reprodutor padrão")
        btn_play.setFixedSize(22, 22)
        btn_play.setCursor(Qt.PointingHandCursor)
        btn_play.setStyleSheet("padding: 0px; font-size: 10px;")
        btn_play.clicked.connect(lambda: open_file(path))

        btn_reveal = QPushButton("📂")
        btn_reveal.setToolTip("Localizar no Explorer")
        btn_reveal.setFixedSize(22, 22)
        btn_reveal.setCursor(Qt.PointingHandCursor)
        btn_reveal.setStyleSheet("padding: 0px; font-size: 10px;")
        btn_reveal.clicked.connect(lambda: reveal_in_explorer(path))

        layout.addWidget(lbl_size)
        layout.addWidget(lbl_name, 1)
        layout.addWidget(btn_play)
        layout.addWidget(btn_reveal)

        return row_frame
