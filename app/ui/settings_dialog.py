import os
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QGroupBox, QTabWidget,
    QInputDialog, QSplitter, QFrame, QScrollArea
)
from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices

from app.core.config import AppConfig
from app.core.database import MediaDatabase
from app.utils.media_helpers import format_file_size


class SettingsDialog(QDialog):
    """Diálogo de gerenciamento de pastas e unidades, indexação, grupos de mídia e informações sobre o projeto."""

    reindex_requested = Signal()
    folder_groups_updated = Signal()

    def __init__(self, config: AppConfig, db: MediaDatabase, default_tab: int = 0, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.setWindowTitle("Configurações & Pastas — MediaFinder")
        self.resize(760, 560)
        self.setMinimumSize(660, 480)
        self.setModal(True)

        self.groups_data: Dict[str, List[str]] = dict(self.config.get_folder_groups())
        self.current_group_name: Optional[str] = None

        self._init_ui()
        self._load_data()

        if 0 <= default_tab < self.tabs.count():
            self.tabs.setCurrentIndex(default_tab)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #242A34;
                border-radius: 6px;
                background-color: #161A21;
            }
            QTabBar::tab {
                background-color: #0E1014;
                color: #94A3B8;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #161A21;
                color: #38BDF8;
                border-bottom: 2px solid #38BDF8;
            }
        """)

        tab_global = self._build_global_folders_tab()
        self.tabs.addTab(tab_global, "📁 Pastas Monitoradas")

        tab_groups = self._build_folder_groups_tab()
        self.tabs.addTab(tab_groups, "🏷️ Grupos de Mídia & Categorias")

        tab_about = self._build_about_tab()
        self.tabs.addTab(tab_about, "ℹ️ Sobre")

        main_layout.addWidget(self.tabs, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        self.btn_reindex = QPushButton("🔄 Reindexar Selecionadas")
        self.btn_reindex.setObjectName("primary_action_btn")
        self.btn_reindex.clicked.connect(self._on_reindex_clicked)
        bottom_layout.addWidget(self.btn_reindex)

        self.btn_clear_db = QPushButton("🗑️ Limpar Banco")
        self.btn_clear_db.clicked.connect(self._on_clear_db_clicked)
        bottom_layout.addWidget(self.btn_clear_db)

        bottom_layout.addStretch(1)

        self.btn_save_close = QPushButton("💾 Salvar e Fechar")
        self.btn_save_close.setObjectName("primary_action_btn")
        self.btn_save_close.clicked.connect(self._on_save_and_close)
        bottom_layout.addWidget(self.btn_save_close)

        main_layout.addLayout(bottom_layout)

    def _build_global_folders_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_desc = QLabel("Indique exclusivamente as pastas que você deseja que o MediaFinder indexe.\nNenhum outro diretório do computador será lido ou catalogado.")
        lbl_desc.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: 500;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        self.list_folders = QListWidget()
        self.list_folders.setStyleSheet("""
            QListWidget {
                background-color: #0E1014;
                border: 1px solid #1E242D;
                border-radius: 6px;
                color: #F8FAFC;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 6px;
                border-bottom: 1px solid #15181E;
            }
        """)
        layout.addWidget(self.list_folders, 1)

        btn_layout = QHBoxLayout()
        self.btn_add_watched = QPushButton("➕ Adicionar Pasta...")
        self.btn_add_watched.setObjectName("primary_action_btn")
        self.btn_add_watched.clicked.connect(self._add_watched_folder)
        btn_layout.addWidget(self.btn_add_watched)

        self.btn_remove_watched = QPushButton("➖ Remover Selecionada")
        self.btn_remove_watched.clicked.connect(self._remove_watched_folder)
        btn_layout.addWidget(self.btn_remove_watched)

        self.btn_clear_all_watched = QPushButton("🗑️ Limpar Todas as Pastas")
        self.btn_clear_all_watched.clicked.connect(self._clear_all_watched_folders)
        btn_layout.addWidget(self.btn_clear_all_watched)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)


        group_stats = QGroupBox("📊 Estatísticas da Base de Dados")
        group_stats.setStyleSheet("""
            QGroupBox {
                border: 1px solid #242A34;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
                color: #38BDF8;
                font-weight: bold;
            }
        """)
        stats_layout = QVBoxLayout(group_stats)
        stats_layout.setSpacing(4)

        self.lbl_stats = QLabel("Total de Arquivos: - | Tamanho Total: -")
        self.lbl_stats.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 12px;")
        stats_layout.addWidget(self.lbl_stats)

        self.lbl_drives_detail = QLabel("Drives: -")
        self.lbl_drives_detail.setStyleSheet("color: #94A3B8; font-size: 11px;")
        stats_layout.addWidget(self.lbl_drives_detail)

        layout.addWidget(group_stats)

        return widget

    def _build_folder_groups_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_desc = QLabel("Crie categorias e equivalências para unir pastas de múltiplos locais ou unidades (ex: 'Filmes' contendo pastas em diferentes discos). Esses grupos alimentam o buscador e o Modo TV automaticamente:")
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 11px;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl_grp_title = QLabel("Categorias / Grupos:")
        lbl_grp_title.setStyleSheet("font-weight: bold; color: #E2E8F0; font-size: 11px;")
        left_layout.addWidget(lbl_grp_title)

        self.list_groups = QListWidget()
        self.list_groups.setStyleSheet("""
            QListWidget {
                background-color: #0E1014;
                border: 1px solid #1E242D;
                border-radius: 6px;
                color: #F8FAFC;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #15181E;
            }
            QListWidget::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
            }
        """)
        self.list_groups.currentTextChanged.connect(self._on_group_selected)
        left_layout.addWidget(self.list_groups, 1)

        grp_btns = QHBoxLayout()
        self.btn_new_group = QPushButton("➕ Novo Grupo")
        self.btn_new_group.clicked.connect(self._add_new_group)
        grp_btns.addWidget(self.btn_new_group)

        self.btn_del_group = QPushButton("🗑️ Excluir")
        self.btn_del_group.clicked.connect(self._delete_group)
        grp_btns.addWidget(self.btn_del_group)

        left_layout.addLayout(grp_btns)
        splitter.addWidget(left_box)

        # Lado Direito: Pastas do Grupo Selecionado
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(6)

        self.lbl_selected_group = QLabel("Pastas Vinculadas a este Grupo:")
        self.lbl_selected_group.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 11px;")
        right_layout.addWidget(self.lbl_selected_group)

        self.list_group_folders = QListWidget()
        self.list_group_folders.setStyleSheet("""
            QListWidget {
                background-color: #0E1014;
                border: 1px solid #1E242D;
                border-radius: 6px;
                color: #CBD5E1;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #15181E;
            }
        """)
        right_layout.addWidget(self.list_group_folders, 1)

        f_btns = QHBoxLayout()
        self.btn_add_folder_to_grp = QPushButton("📁 Adicionar Pasta...")
        self.btn_add_folder_to_grp.clicked.connect(self._add_folder_to_group)
        f_btns.addWidget(self.btn_add_folder_to_grp)

        self.btn_import_subfolder = QPushButton("📑 Escolher Subpasta...")
        self.btn_import_subfolder.clicked.connect(self._import_subfolder_to_group)
        f_btns.addWidget(self.btn_import_subfolder)

        self.btn_del_folder_from_grp = QPushButton("🗑️ Remover")
        self.btn_del_folder_from_grp.clicked.connect(self._remove_folder_from_group)
        f_btns.addWidget(self.btn_del_folder_from_grp)

        right_layout.addLayout(f_btns)
        splitter.addWidget(right_box)

        splitter.setStretchFactor(0, 35)
        splitter.setStretchFactor(1, 65)

        layout.addWidget(splitter, 1)
        return widget

    def _build_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Card Principal Estilizado e Limpo (com ID específico para não vazar bordas aos QLabels)
        info_card = QFrame()
        info_card.setObjectName("about_main_card")
        info_card.setStyleSheet("""
            QFrame#about_main_card {
                background-color: #12151B;
                border: 1px solid #242A34;
                border-radius: 10px;
                padding: 18px;
            }
            QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        card_layout = QVBoxLayout(info_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Header do App
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        lbl_badge = QLabel("⚡")
        lbl_badge.setStyleSheet("font-size: 32px; background-color: #1E293B; border-radius: 8px; padding: 6px 10px; color: #38BDF8;")
        top_row.addWidget(lbl_badge)

        v_titles = QVBoxLayout()
        v_titles.setSpacing(3)
        lbl_app_name = QLabel("MediaFinder — Buscador Rápido de Mídias & Central de TV")
        lbl_app_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC;")
        v_titles.addWidget(lbl_app_name)

        lbl_version = QLabel("Versão 1.0.0 • Release Oficial Open Source")
        lbl_version.setStyleSheet("font-size: 12px; color: #38BDF8; font-weight: 600;")
        v_titles.addWidget(lbl_version)

        top_row.addLayout(v_titles, 1)
        card_layout.addLayout(top_row)

        # Linha Divisória Fina
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: #1E2530; border: none; max-height: 1px; margin: 4px 0;")
        card_layout.addWidget(div)

        # Detalhes do Autor e Licença em layout limpo
        details_layout = QVBoxLayout()
        details_layout.setSpacing(8)

        lbl_author = QLabel("👤 <b>Desenvolvedor:</b> Jairo Ivo (<a href='https://github.com/xToshiro' style='color: #38BDF8; text-decoration: none;'>@xToshiro</a>)")
        lbl_author.setOpenExternalLinks(True)
        lbl_author.setStyleSheet("font-size: 13px; color: #E2E8F0;")
        details_layout.addWidget(lbl_author)

        lbl_repo = QLabel("🌐 <b>Repositório Oficial:</b> <a href='https://github.com/xToshiro/MediaFinder' style='color: #38BDF8; text-decoration: underline;'>https://github.com/xToshiro/MediaFinder</a>")
        lbl_repo.setOpenExternalLinks(True)
        lbl_repo.setStyleSheet("font-size: 13px; color: #E2E8F0;")
        details_layout.addWidget(lbl_repo)

        lbl_license = QLabel("⚖️ <b>Licença:</b> GNU General Public License v3.0 (GPLv3) — Software Livre & Código Aberto")
        lbl_license.setStyleSheet("font-size: 13px; color: #34D399; font-weight: 500;")
        details_layout.addWidget(lbl_license)

        lbl_tech = QLabel("🛠️ <b>Tecnologias:</b> Python 3, PySide6 (Qt 6), SQLite3 WAL + FTS5, Pillow (PIL), PyInstaller")
        lbl_tech.setStyleSheet("font-size: 12px; color: #94A3B8;")
        details_layout.addWidget(lbl_tech)

        card_layout.addLayout(details_layout)

        # Linha com Botões de Ação dentro do Card
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        btn_box.setContentsMargins(0, 8, 0, 0)

        self.btn_open_repo = QPushButton("🌐 Abrir no GitHub")
        self.btn_open_repo.setObjectName("primary_action_btn")
        self.btn_open_repo.setCursor(Qt.PointingHandCursor)
        self.btn_open_repo.setStyleSheet("padding: 7px 16px; font-size: 12px;")
        self.btn_open_repo.clicked.connect(self._open_github_repo)
        btn_box.addWidget(self.btn_open_repo)

        self.btn_copy_repo_link = QPushButton("📋 Copiar Link")
        self.btn_copy_repo_link.setStyleSheet("padding: 7px 14px; font-size: 12px; background-color: #1E232B; color: #E2E8F0; border: 1px solid #2D3748; border-radius: 6px;")
        self.btn_copy_repo_link.clicked.connect(self._copy_repo_link)
        btn_box.addWidget(self.btn_copy_repo_link)

        btn_box.addStretch()
        card_layout.addLayout(btn_box)

        layout.addWidget(info_card)
        layout.addStretch(1)
        return widget


    def _open_github_repo(self):
        QDesktopServices.openUrl(QUrl("https://github.com/xToshiro/MediaFinder"))

    def _copy_repo_link(self):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText("https://github.com/xToshiro/MediaFinder")
            QMessageBox.information(self, "Copiado", "Link do repositório copiado para a área de transferência!")

    def _load_data(self):
        """Carrega pastas monitoradas, grupos e estatísticas."""
        # 1. Pastas monitoradas
        self.list_folders.clear()
        folders = self.config.get_watched_folders()
        if not folders:
            placeholder = QListWidgetItem("Nenhuma pasta configurada. Clique em '➕ Adicionar Pasta...' abaixo.")
            placeholder.setForeground(Qt.gray)
            self.list_folders.addItem(placeholder)
        else:
            for f in folders:
                exists = os.path.exists(f)
                prefix = "📁 " if exists else "⚠️ "
                suffix = "" if exists else " (não acessível / desconectado)"
                item = QListWidgetItem(f"{prefix}{f}{suffix}")
                item.setData(Qt.UserRole, f)
                if not exists:
                    item.setForeground(Qt.yellow)
                self.list_folders.addItem(item)


        # 2. Grupos de pastas
        self.groups_data = dict(self.config.get_folder_groups())
        self._populate_groups_list()

        # 3. Estatísticas
        stats = self.db.get_stats()
        total_files = stats.get("total_files", 0)
        total_size = stats.get("total_size", 0)
        drives = stats.get("drives", {})

        self.lbl_stats.setText(f"Total Indexado: {total_files:,} arquivos ({format_file_size(total_size)})")
        drives_str = ", ".join([f"{k} ({v} arquivos)" for k, v in drives.items() if k])
        self.lbl_drives_detail.setText(f"Drives Ativos: {drives_str if drives_str else 'Nenhum'}")

    def _populate_groups_list(self):
        self.list_groups.clear()
        for grp in self.groups_data.keys():
            self.list_groups.addItem(grp)
        if self.groups_data:
            self.list_groups.setCurrentRow(0)

    def _on_group_selected(self, group_name: str):
        self.current_group_name = group_name
        self.list_group_folders.clear()
        if not group_name or group_name not in self.groups_data:
            self.lbl_selected_group.setText("Selecione um grupo à esquerda")
            return

        self.lbl_selected_group.setText(f"Pastas vinculadas ao grupo '{group_name}':")
        for f in self.groups_data[group_name]:
            self.list_group_folders.addItem(f)

    def _add_new_group(self):
        name, ok = QInputDialog.getText(self, "Novo Grupo de Mídia", "Nome da categoria ou grupo (ex: Cursos, Novelas, Filmes 4K):")
        if ok and name.strip():
            clean_name = name.strip()
            if clean_name in self.groups_data:
                QMessageBox.warning(self, "Aviso", "Já existe um grupo com este nome.")
                return
            self.groups_data[clean_name] = []
            self._populate_groups_list()
            items = self.list_groups.findItems(clean_name, Qt.MatchExactly)
            if items:
                self.list_groups.setCurrentItem(items[0])

    def _delete_group(self):
        if not self.current_group_name or self.current_group_name not in self.groups_data:
            return

        reply = QMessageBox.question(
            self,
            "Excluir Grupo",
            f"Deseja realmente remover o grupo '{self.current_group_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.groups_data[self.current_group_name]
            self._populate_groups_list()

    def _add_folder_to_group(self):
        if not self.current_group_name or self.current_group_name not in self.groups_data:
            return

        folder = QFileDialog.getExistingDirectory(self, f"Selecionar Pasta para '{self.current_group_name}'")
        if folder:
            norm = os.path.normpath(folder)
            if norm not in self.groups_data[self.current_group_name]:
                self.groups_data[self.current_group_name].append(norm)
                self.list_group_folders.addItem(norm)

    def _import_subfolder_to_group(self):
        """Permite escolher uma das subpastas conhecidas indexadas no banco com facilidade."""
        if not self.current_group_name or self.current_group_name not in self.groups_data:
            return

        known_subfolders = self.db.get_indexed_subfolders(limit=300)
        if not known_subfolders:
            QMessageBox.information(self, "Aviso", "Nenhuma subpasta indexada encontrada no banco de dados.")
            return

        item, ok = QInputDialog.getItem(
            self,
            "Escolher Subpasta Indexada",
            "Selecione uma pasta indexada para vincular a este grupo:",
            known_subfolders,
            0,
            False
        )
        if ok and item:
            norm = os.path.normpath(item)
            if norm not in self.groups_data[self.current_group_name]:
                self.groups_data[self.current_group_name].append(norm)
                self.list_group_folders.addItem(norm)

    def _remove_folder_from_group(self):
        if not self.current_group_name or self.current_group_name not in self.groups_data:
            return

        row = self.list_group_folders.currentRow()
        if row >= 0:
            del self.groups_data[self.current_group_name][row]
            self.list_group_folders.takeItem(row)

    def _add_watched_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Indexar")
        if folder:
            norm = os.path.normpath(folder)
            folders = self.config.get_watched_folders()
            if norm not in folders:
                folders.append(norm)
                self.config.set_watched_folders(folders)
                self._load_data()

    def _remove_watched_folder(self):
        current_item = self.list_folders.currentItem()
        if not current_item:
            return

        folder = current_item.data(Qt.UserRole)
        if not folder:
            return

        folders = self.config.get_watched_folders()
        if folder in folders:
            folders.remove(folder)
            self.config.set_watched_folders(folders)
            # Remove arquivos dessa pasta do banco de dados imediatamente
            self.db.remove_folder_records(folder)
            self._load_data()

    def _clear_all_watched_folders(self):
        folders = self.config.get_watched_folders()
        if not folders:
            return

        reply = QMessageBox.question(
            self,
            "Limpar Todas as Pastas",
            "Deseja remover todas as pastas da lista e limpar os registros correspondentes do catálogo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.set_watched_folders([])
            self.db.clear_database()
            self._load_data()


    def _on_reindex_clicked(self):
        self._on_save_and_close()
        self.reindex_requested.emit()

    def _on_clear_db_clicked(self):
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "Deseja realmente limpar todos os registros indexados do banco de dados?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.clear_database()
            self._load_data()
            QMessageBox.information(self, "Sucesso", "Banco de dados limpo com sucesso.")

    def _on_save_and_close(self):
        self.config.set_folder_groups(self.groups_data)
        self.folder_groups_updated.emit()
        self.accept()
