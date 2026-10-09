import os
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QGridLayout
)
from PySide6.QtCore import Qt

from app.core.database import MediaDatabase
from app.utils.media_helpers import format_file_size
from app.utils.system_ops import open_file, reveal_in_explorer


def format_duration_readable(seconds: int) -> str:
    """Formata segundos em uma representação limpa (ex: '153d 11h' ou '4h 22m')."""
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

    return " ".join(parts[:2]) if len(parts) > 2 else " ".join(parts)


class StatsDialog(QDialog):
    """Painel elegante e minimalista de estatísticas e métricas da biblioteca de mídias."""

    CATEGORY_COLORS = {
        "video": "#38BDF8",     # Ciano
        "audio": "#34D399",     # Esmeralda
        "image": "#FBBF24",     # Âmbar
        "document": "#A78BFA",  # Roxo
        "other": "#94A3B8"      # Cinza
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
        self.setWindowTitle("Estatísticas da Biblioteca — MediaFinder")
        self.resize(760, 600)
        self.setMinimumSize(640, 480)
        self.setModal(True)

        self._init_ui()
        self._load_stats()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Cabeçalho Superior
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        lbl_title = QLabel("📊 Panorama Geral da Biblioteca")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #FFFFFF; border: none; background: transparent;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch(1)

        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1E232B;
                color: #94A3B8;
                border: 1px solid #2D3748;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2D3748;
                color: #FFFFFF;
            }
        """)
        btn_refresh.clicked.connect(self._load_stats)
        header_layout.addWidget(btn_refresh)

        main_layout.addLayout(header_layout)

        # Área de Rolagem com Fundo Limpo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #0E1014;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #242A34;
                border-radius: 4px;
                min-height: 24px;
            }
        """)

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 6, 0)
        self.content_layout.setSpacing(18)

        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll, 1)

        # Rodapé com Botão Fechar
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)
        btn_close = QPushButton("Fechar")
        btn_close.setObjectName("primary_action_btn")
        btn_close.setFixedSize(110, 34)
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)
        main_layout.addLayout(bottom_layout)

    def _load_stats(self):
        """Renderiza cards e barras com visual limpo e sem bordas aninhadas."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

        stats = self.db.get_detailed_stats()
        total_files = stats.get("total_files", 0)
        total_size = stats.get("total_size", 0)
        total_duration = stats.get("total_duration", 0)
        total_drives = stats.get("total_drives", 0)

        # 1. Cards KPI Superiores (Grid 4 colunas)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        card_files = self._build_clean_kpi_card("📁 Total de Mídias", f"{total_files:,}", "arquivos indexados")
        card_size = self._build_clean_kpi_card("💾 Espaço em Disco", format_file_size(total_size), "volume acumulado")
        card_dur = self._build_clean_kpi_card("⏱️ Duração Total", format_duration_readable(total_duration), "conteúdo contínuo")
        card_drives = self._build_clean_kpi_card("💽 Volumes Monitorados", f"{total_drives} Drive(s)", "discos ativos")

        cards_grid.addWidget(card_files, 0, 0)
        cards_grid.addWidget(card_size, 0, 1)
        cards_grid.addWidget(card_dur, 0, 2)
        cards_grid.addWidget(card_drives, 0, 3)
        self.content_layout.addLayout(cards_grid)

        # 2. Seção: Distribuição por Categoria
        lbl_cat_header = QLabel("📂 Distribuição por Categoria")
        lbl_cat_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #94A3B8; border: none; background: transparent; padding-top: 6px;")
        self.content_layout.addWidget(lbl_cat_header)

        cat_container = QFrame()
        cat_container.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #232936;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        cat_layout = QVBoxLayout(cat_container)
        cat_layout.setContentsMargins(16, 14, 16, 14)
        cat_layout.setSpacing(12)

        categories = stats.get("categories", [])
        for cat_data in categories:
            cat_name = cat_data.get("category", "other")
            count = cat_data.get("count", 0)
            size = cat_data.get("total_size", 0)
            duration = cat_data.get("total_duration", 0)

            pct_size = (size / total_size * 100) if total_size > 0 else 0
            color = self.CATEGORY_COLORS.get(cat_name, "#94A3B8")
            display_name = self.CATEGORY_NAMES.get(cat_name, cat_name.title())

            row = self._build_progress_row(
                title=display_name,
                primary_info=f"{count:,} itens ({format_file_size(size)} — {pct_size:.1f}%)",
                secondary_info=f"⏱️ {format_duration_readable(duration)}" if duration > 0 else "",
                percentage=pct_size,
                bar_color=color
            )
            cat_layout.addWidget(row)

        self.content_layout.addWidget(cat_container)

        # 3. Seção: Armazenamento por Disco/Volume
        lbl_drive_header = QLabel("💽 Armazenamento por Unidade de Disco")
        lbl_drive_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #94A3B8; border: none; background: transparent; padding-top: 6px;")
        self.content_layout.addWidget(lbl_drive_header)

        drive_container = QFrame()
        drive_container.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #232936;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        drive_layout = QVBoxLayout(drive_container)
        drive_layout.setContentsMargins(16, 14, 16, 14)
        drive_layout.setSpacing(12)

        drives = stats.get("drives", [])
        for drv_data in drives:
            drive_letter = drv_data.get("drive", "")
            count = drv_data.get("count", 0)
            size = drv_data.get("total_size", 0)
            pct_size = (size / total_size * 100) if total_size > 0 else 0

            row = self._build_progress_row(
                title=f"Unidade {drive_letter}",
                primary_info=f"{format_file_size(size)} ({count:,} arquivos)",
                secondary_info=f"{pct_size:.1f}% do acervo",
                percentage=pct_size,
                bar_color="#38BDF8"
            )
            drive_layout.addWidget(row)

        self.content_layout.addWidget(drive_container)

        # 4. Grid Inferior: Top Extensões & Maiores Arquivos
        bottom_grid = QGridLayout()
        bottom_grid.setSpacing(14)

        # Top Extensões
        ext_box = QFrame()
        ext_box.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #232936;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        ext_layout = QVBoxLayout(ext_box)
        ext_layout.setContentsMargins(14, 12, 14, 12)
        ext_layout.setSpacing(8)

        lbl_ext_title = QLabel("🏷️ Formatos Mais Frequentes")
        lbl_ext_title.setStyleSheet("font-weight: bold; color: #E2E8F0; font-size: 12px; margin-bottom: 4px;")
        ext_layout.addWidget(lbl_ext_title)

        top_exts = stats.get("top_extensions", [])
        for ext_data in top_exts[:6]:
            ext_name = ext_data.get("extension", "")
            count = ext_data.get("count", 0)
            size = ext_data.get("total_size", 0)

            ext_row = QHBoxLayout()
            lbl_tag = QLabel(ext_name.upper())
            lbl_tag.setStyleSheet("""
                background-color: #1F242D;
                color: #38BDF8;
                padding: 2px 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            """)
            lbl_tag_info = QLabel(f"{count:,} arquivos ({format_file_size(size)})")
            lbl_tag_info.setStyleSheet("color: #94A3B8; font-size: 11px;")
            ext_row.addWidget(lbl_tag)
            ext_row.addWidget(lbl_tag_info)
            ext_row.addStretch(1)
            ext_layout.addLayout(ext_row)

        bottom_grid.addWidget(ext_box, 0, 0)

        # Maiores Arquivos
        large_box = QFrame()
        large_box.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #232936;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        large_layout = QVBoxLayout(large_box)
        large_layout.setContentsMargins(14, 12, 14, 12)
        large_layout.setSpacing(6)

        lbl_large_title = QLabel("🐘 Maiores Arquivos do Catálogo")
        lbl_large_title.setStyleSheet("font-weight: bold; color: #E2E8F0; font-size: 12px; margin-bottom: 4px;")
        large_layout.addWidget(lbl_large_title)

        largest_files = stats.get("largest_files", [])
        for f in largest_files[:4]:
            item_widget = self._build_large_file_item(f)
            large_layout.addWidget(item_widget)

        bottom_grid.addWidget(large_box, 0, 1)
        self.content_layout.addLayout(bottom_grid)

    def _build_clean_kpi_card(self, title: str, value: str, subtitle: str) -> QFrame:
        """Cria um card KPI totalmente limpo, sem caixas internas nem bordas aninhadas."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161A21;
                border: 1px solid #232936;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
        
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold;")

        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet("color: #64748B; font-size: 10px;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        layout.addWidget(lbl_sub)

        return card

    def _build_progress_row(self, title: str, primary_info: str, secondary_info: str, percentage: float, bar_color: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        info_layout = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #F1F5F9; font-weight: 600; font-size: 12px;")

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
        pbar.setValue(max(1, int(percentage)))
        pbar.setTextVisible(False)
        pbar.setFixedHeight(6)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0E1014;
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 3px;
            }}
        """)

        layout.addLayout(info_layout)
        layout.addWidget(pbar)

        return widget

    def _build_large_file_item(self, file_data: Dict[str, Any]) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        name = file_data.get("name", "")
        size_str = format_file_size(file_data.get("size", 0))
        path = file_data.get("path", "")

        lbl_size = QLabel(size_str)
        lbl_size.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px;")

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("color: #CBD5E1; font-size: 11px;")
        lbl_name.setToolTip(path)

        btn_play = QPushButton("▶")
        btn_play.setToolTip("Abrir no reprodutor padrão")
        btn_play.setFixedSize(20, 20)
        btn_play.setCursor(Qt.PointingHandCursor)
        btn_play.setStyleSheet("""
            QPushButton {
                background-color: #1F242D;
                color: #FFFFFF;
                border: 1px solid #2D3748;
                border-radius: 4px;
                font-size: 9px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2563EB;
                border-color: #3B82F6;
            }
        """)
        btn_play.clicked.connect(lambda: open_file(path))

        btn_reveal = QPushButton("📂")
        btn_reveal.setToolTip("Localizar no Explorer")
        btn_reveal.setFixedSize(20, 20)
        btn_reveal.setCursor(Qt.PointingHandCursor)
        btn_reveal.setStyleSheet("""
            QPushButton {
                background-color: #1F242D;
                color: #FFFFFF;
                border: 1px solid #2D3748;
                border-radius: 4px;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2D3748;
            }
        """)
        btn_reveal.clicked.connect(lambda: reveal_in_explorer(path))

        layout.addWidget(lbl_size)
        layout.addWidget(lbl_name, 1)
        layout.addWidget(btn_play)
        layout.addWidget(btn_reveal)

        return row
