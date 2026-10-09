import os
import sys
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QProgressBar, QStatusBar, QMessageBox, QApplication,
    QMenu, QSystemTrayIcon, QStyle
)
from PySide6.QtCore import Qt, QTimer, QSize, QPoint
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QAction

from app.core.config import AppConfig
from app.core.database import MediaDatabase
from app.core.scanner import IndexWorker
from app.ui.search_bar import SearchBar
from app.ui.filter_bar import FilterBar
from app.ui.results_view import ResultsTableView
from app.ui.preview_panel import PreviewPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.random_dialog import RandomMediaDialog
from app.ui.tv_mode_window import TVModeWindow
from app.ui.stats_dialog import StatsDialog
from app.utils.media_helpers import format_file_size
from app.utils.system_ops import open_file


class MainWindow(QMainWindow):
    """Janela principal do MediaFinder."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaFinder — Buscador Rápido de Mídias")

        # Inicializa configurações e banco
        self.config = AppConfig()
        self.db = MediaDatabase()
        self.worker: Optional[IndexWorker] = None
        self.tv_window: Optional[TVModeWindow] = None
        self.tray_icon: Optional[QSystemTrayIcon] = None

        # Configura dimensões da janela salvas
        w = self.config.get("window_width", 1100)
        h = self.config.get("window_height", 680)
        self.resize(w, h)
        self.setMinimumSize(640, 420)
        if self.config.get("window_maximized", False):
            self.showMaximized()

        self._current_query = self.config.get("last_search_query", "")
        self._current_category = self.config.get("last_category_filter", "all")
        self._current_drive = self.config.get("last_drive_filter", "all")
        self._current_sort = "name_asc"
        self._preview_visible = self.config.get("preview_visible", True)

        self._init_ui()
        self._init_system_tray()
        self._setup_shortcuts()
        self._restore_previous_state()

        if self.config.get("auto_scan_on_startup", True):
            QTimer.singleShot(400, self.start_indexing)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 8)
        main_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        lbl_app_logo = QLabel("⚡ MediaFinder")
        lbl_app_logo.setStyleSheet("font-size: 17px; font-weight: bold; color: #38BDF8; padding-right: 4px;")
        header_layout.addWidget(lbl_app_logo)

        self.search_bar = SearchBar()
        self.search_bar.search_changed.connect(self._on_search_text_changed)
        self.search_bar.reindex_requested.connect(self.start_indexing)
        header_layout.addWidget(self.search_bar, 1)

        self.btn_random = QPushButton("🎲 Aleatório")
        self.btn_random.setObjectName("random_mode_btn")
        self.btn_random.setToolTip("Sorteia e abre uma mídia aleatória imediatamente (F4 / Ctrl+R)\nClique com botão direito para configurar pastas.")
        self.btn_random.clicked.connect(self._trigger_quick_random)
        self.btn_random.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_random.customContextMenuRequested.connect(self._show_random_menu)
        header_layout.addWidget(self.btn_random)

        self.btn_tv_mode = QPushButton("📺 Modo TV")
        self.btn_tv_mode.setObjectName("tv_mode_btn")
        self.btn_tv_mode.setToolTip("Abre o Modo TV com canais automáticos, grade de 24h e player integrado (F8 / Ctrl+T)")
        self.btn_tv_mode.clicked.connect(self._open_tv_mode)
        header_layout.addWidget(self.btn_tv_mode)

        self.btn_stats = QPushButton("📊 Estatísticas")
        self.btn_stats.setToolTip("Visualizar panorama, gráficos e métricas da biblioteca (F9 / Ctrl+I)")
        self.btn_stats.clicked.connect(self._open_stats_dialog)
        header_layout.addWidget(self.btn_stats)

        self.btn_toggle_preview = QPushButton("👁️ Prévia")
        self.btn_toggle_preview.setCheckable(True)
        self.btn_toggle_preview.setChecked(self._preview_visible)
        self.btn_toggle_preview.setToolTip("Mostrar/Ocultar painel lateral de prévia (Ctrl+P)")
        self.btn_toggle_preview.clicked.connect(self._toggle_preview_panel)
        header_layout.addWidget(self.btn_toggle_preview)

        self.btn_settings = QPushButton("⚙️ Pastas")
        self.btn_settings.setToolTip("Gerenciar pastas e unidades monitoradas, indexação e grupos de mídia")
        self.btn_settings.clicked.connect(self._open_settings)
        header_layout.addWidget(self.btn_settings)

        self.btn_about = QPushButton("ℹ️ Sobre")
        self.btn_about.setToolTip("Informações sobre o MediaFinder, autor e licença")
        self.btn_about.clicked.connect(self._open_about)
        header_layout.addWidget(self.btn_about)

        main_layout.addLayout(header_layout)

        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        main_layout.addWidget(self.filter_bar)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(True)

        self.results_table = ResultsTableView()
        self.results_table.item_selected.connect(self._on_item_selected)
        self.results_table.delete_requested.connect(self._on_delete_files_requested)
        self.splitter.addWidget(self.results_table)

        self.preview_panel = PreviewPanel()
        self.preview_panel.close_requested.connect(lambda: self._toggle_preview_panel(False))
        self.splitter.addWidget(self.preview_panel)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.preview_panel.setVisible(self._preview_visible)
        main_layout.addWidget(self.splitter, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_status_results = QLabel("Pronto")
        self.status_bar.addWidget(self.lbl_status_results, 1)

        self.lbl_scan_status = QLabel("")
        self.lbl_scan_status.setStyleSheet("color: #38BDF8; font-weight: 500;")
        self.status_bar.addPermanentWidget(self.lbl_scan_status)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setMaximumWidth(140)
        self.scan_progress_bar.setMaximumHeight(14)
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.scan_progress_bar)

    def _init_system_tray(self):
        """Inicializa a bandeja do sistema (Windows System Tray) com menu de acesso rápido."""
        base_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
        icon_path = os.path.join(base_dir, "assets", "icon.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_dir, "assets", "icon.ico")

        if os.path.exists(icon_path):
            self.app_icon = QIcon(icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = self.style().standardIcon(QStyle.SP_DesktopIcon)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self.app_icon, self)
            self.tray_icon.setToolTip("MediaFinder — Buscador de Mídias & Modo TV")

            tray_menu = QMenu()
            tray_menu.setStyleSheet("""
                QMenu {
                    background-color: #161A21;
                    border: 1px solid #242A34;
                    color: #FFFFFF;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 18px;
                    border-radius: 4px;
                }
                QMenu::item:selected {
                    background-color: #2563EB;
                }
            """)

            act_open = tray_menu.addAction("⚡ Abrir MediaFinder")
            act_open.triggered.connect(self._restore_from_tray)

            act_tv = tray_menu.addAction("📺 Modo TV (Canais ao Vivo)")
            act_tv.triggered.connect(self._open_tv_mode)

            act_random = tray_menu.addAction("🎲 Sorteio Aleatório (F4)")
            act_random.triggered.connect(self._trigger_quick_random)

            act_stats = tray_menu.addAction("📊 Estatísticas da Biblioteca (F9)")
            act_stats.triggered.connect(self._open_stats_dialog)

            tray_menu.addSeparator()

            act_settings = tray_menu.addAction("⚙️ Gerenciar Pastas & Fontes...")
            act_settings.triggered.connect(self._open_settings)

            act_about = tray_menu.addAction("ℹ️ Sobre o MediaFinder...")
            act_about.triggered.connect(self._open_about)

            tray_menu.addSeparator()

            act_quit = tray_menu.addAction("✕ Sair do MediaFinder")

            act_quit.triggered.connect(self._quit_application)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def _quit_application(self):
        if self.tv_window and self.tv_window.isVisible():
            self.tv_window.close()
        QApplication.quit()

    def _setup_shortcuts(self):
        """Configura atalhos globais da aplicação."""
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_bar.focus_input)
        QShortcut(QKeySequence("F3"), self, activated=self.search_bar.focus_input)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=lambda: self._toggle_preview_panel(not self.preview_panel.isVisible()))
        QShortcut(QKeySequence("F5"), self, activated=self.start_indexing)
        QShortcut(QKeySequence("F4"), self, activated=self._trigger_quick_random)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._trigger_quick_random)
        QShortcut(QKeySequence("F8"), self, activated=self._open_tv_mode)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._open_tv_mode)
        QShortcut(QKeySequence("F9"), self, activated=self._open_stats_dialog)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self._open_stats_dialog)

    def _restore_previous_state(self):
        self._update_drives_list()
        self.filter_bar.set_category(self._current_category)
        self.filter_bar.set_drive(self._current_drive)
        self.search_bar.set_text(self._current_query)
        self.perform_search()

    def _update_drives_list(self):
        stats = self.db.get_stats()
        drives = list(stats.get("drives", {}).keys())
        self.filter_bar.set_available_drives(drives)

    def _on_search_text_changed(self, query: str):
        self._current_query = query
        self.config.set("last_search_query", query)
        self.perform_search()

    def _on_filters_changed(self, category: str, drive: str, sort_by: str):
        self._current_category = category
        self._current_drive = drive
        self._current_sort = sort_by

        self.config.set("last_category_filter", category)
        self.config.set("last_drive_filter", drive)
        self.perform_search()

    def _toggle_preview_panel(self, visible: Optional[bool] = None):
        if visible is None:
            visible = not self.preview_panel.isVisible()
        self.preview_panel.setVisible(visible)
        self.btn_toggle_preview.setChecked(visible)
        self.config.set("preview_visible", visible)

    def perform_search(self):
        files, total_count, total_size = self.db.search_files(
            query=self._current_query,
            category=self._current_category,
            drive=self._current_drive,
            sort_by=self._current_sort,
            limit=1000
        )
        self.results_table.set_results(files)

        query_desc = f' para "{self._current_query}"' if self._current_query else ""
        if len(files) < total_count:
            self.lbl_status_results.setText(
                f"Exibindo {len(files):,} de {total_count:,} arquivos encontrados{query_desc} (Total: {format_file_size(total_size)})"
            )
        else:
            self.lbl_status_results.setText(
                f"{total_count:,} arquivos encontrados{query_desc} (Total: {format_file_size(total_size)})"
            )

        if not files:
            self.preview_panel.set_file_data(None)

    def _on_item_selected(self, file_data: dict):
        self.preview_panel.set_file_data(file_data)

    def _on_delete_files_requested(self, files: List[Dict[str, Any]]):
        """Solicita confirmação e apaga permanentemente os arquivos selecionados do disco e do banco."""
        if not files:
            return

        count = len(files)
        total_size = sum(f.get("size", 0) for f in files)
        size_str = format_file_size(total_size)

        if count == 1:
            f = files[0]
            msg = (
                f"Tem certeza de que deseja EXCLUIR permanentemente do disco o arquivo:\n\n"
                f"📄 {f.get('name', '')}\n"
                f"📁 Local: {f.get('path', '')}\n"
                f"💾 Tamanho: {size_str}\n\n"
                f"⚠️ ATENÇÃO: O arquivo será apagado fisicamente da pasta e não poderá ser recuperado!"
            )
        else:
            sample_names = "\n".join(f"• {f.get('name', '')}" for f in files[:5])
            if count > 5:
                sample_names += f"\n• ... e mais {count - 5} arquivo(s)"

            msg = (
                f"Tem certeza de que deseja EXCLUIR permanentemente do disco os {count} arquivos selecionados?\n\n"
                f"💾 Espaço total a ser liberado: {size_str}\n\n"
                f"Arquivos a serem apagados:\n{sample_names}\n\n"
                f"⚠️ ATENÇÃO: Os arquivos serão apagados fisicamente das pastas dos seus discos/unidades!"
            )

        reply = QMessageBox.warning(
            self,
            "⚠️ Confirmar Exclusão Definitiva",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        deleted_paths = []
        failed_files = []

        for f in files:
            path = f.get("path", "")
            if not path:
                continue
            try:
                if os.path.exists(path):
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                deleted_paths.append(path)
            except Exception as e:
                failed_files.append((f.get("name", ""), str(e)))

        # Remove do banco de dados
        if deleted_paths:
            self.db.delete_files_by_paths(deleted_paths)
            self.lbl_status_results.setText(f"🗑️ {len(deleted_paths)} arquivo(s) excluído(s) do disco com sucesso ({size_str} liberados).")
            self._update_drives_list()
            self.perform_search()

        if failed_files:
            fail_msg = "\n".join(f"• {name}: {err}" for name, err in failed_files[:10])
            QMessageBox.critical(
                self,
                "Erro ao Excluir Alguns Arquivos",
                f"Não foi possível excluir {len(failed_files)} arquivo(s) (eles podem estar em uso por outro programa):\n\n{fail_msg}"
            )

    def start_indexing(self):
        """Inicia varredura em segundo plano das pastas e unidades monitoradas."""
        if self.worker and self.worker.isRunning():
            return

        folders = self.config.get_watched_folders()
        if not folders:
            self.scan_progress_bar.setVisible(False)
            self.lbl_scan_status.setText("")
            return

        self.scan_progress_bar.setVisible(True)
        self.scan_progress_bar.setRange(0, 0)
        self.lbl_scan_status.setText("Indexando mídias...")

        if hasattr(self, 'search_bar') and hasattr(self.search_bar, 'btn_reindex'):
            self.search_bar.btn_reindex.setEnabled(False)

        try:
            self.worker = IndexWorker(folders=folders, db=self.db, parent=self)
            if hasattr(self.worker, 'detailed_progress'):
                self.worker.detailed_progress.connect(self._on_indexing_detailed_progress)
            self.worker.progress_changed.connect(self._on_indexing_progress)
            self.worker.finished.connect(self._on_indexing_finished)
            self.worker.error_occurred.connect(self._on_indexing_error)
            self.worker.start()
        except Exception as e:
            self.scan_progress_bar.setVisible(False)
            self.lbl_scan_status.setText("")
            if hasattr(self, 'search_bar') and hasattr(self.search_bar, 'btn_reindex'):
                self.search_bar.btn_reindex.setEnabled(True)

    def _on_indexing_detailed_progress(self, stage: str, current: int, total: int, item_name: str):
        if stage == "scan":
            self.scan_progress_bar.setRange(0, 0)
            self.lbl_scan_status.setText(f"📁 Varrendo: {current:,} arquivos...")
        elif stage == "duration":
            if total > 0:
                self.scan_progress_bar.setRange(0, total)
                self.scan_progress_bar.setValue(current)
                pct = int((current / total) * 100)
                self.lbl_scan_status.setText(f"⏱️ Duração: {current:,}/{total:,} ({pct}%)")
            else:
                self.scan_progress_bar.setRange(0, 0)
                self.lbl_scan_status.setText("⏱️ Calculando durações...")

    def _on_indexing_progress(self, current_path: str, count: int):
        pass

    def _on_indexing_finished(self, total_indexed: int, elapsed: float = 0.0, stats: dict = None):
        self.scan_progress_bar.setVisible(False)
        self.lbl_scan_status.setText("")
        total_files = stats.get("total_files", total_indexed) if isinstance(stats, dict) else total_indexed
        self.lbl_status_results.setText(
            f"Varredura concluída: {total_indexed:,} arquivos processados em {elapsed:.1f}s (Total no catálogo: {total_files:,} mídias)."
        )
        self._update_drives_list()
        self.perform_search()

        if hasattr(self, 'search_bar') and hasattr(self.search_bar, 'btn_reindex'):
            self.search_bar.btn_reindex.setEnabled(True)

    def _on_indexing_error(self, folder: str, err_msg: str):
        pass

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self.db, default_tab=0, parent=self)
        if dialog.exec():
            self._update_drives_list()
            self.perform_search()
            self.start_indexing()

    def _open_about(self):
        dialog = SettingsDialog(self.config, self.db, default_tab=2, parent=self)
        dialog.exec()

    def _open_stats_dialog(self):
        """Abre o painel visual com métricas, gráficos e panorama da biblioteca."""
        dialog = StatsDialog(self.db, self)
        dialog.exec()


    def _open_random_settings(self):
        dialog = RandomMediaDialog(self.config, self.db, self)
        dialog.exec()

    def _show_random_menu(self, pos):
        menu = QMenu(self)
        act_play = menu.addAction("🎲 Sortear e Reproduzir Agora (F4)")
        act_play.triggered.connect(self._trigger_quick_random)
        menu.addSeparator()
        act_config = menu.addAction("⚙️ Configurar Pastas do Aleatório...")
        act_config.triggered.connect(self._open_random_settings)
        menu.exec(self.btn_random.mapToGlobal(pos))

    def _trigger_quick_random(self):
        """Dispara o sorteio aleatório rápido e abre diretamente no reprodutor padrão."""
        import random
        source = self.config.get("random_mode_source", "custom")
        cat = self.config.get("random_mode_category", "video")
        item = None

        if source == "current_results" and self.results_table.files_data:
            item = random.choice(self.results_table.files_data)
        else:
            folders = self.config.get("random_mode_folders", [])
            categories = [cat] if cat and cat != "all" else None
            item = self.db.get_random_file(categories=categories, folders=folders)

        if item:
            self._on_random_media_opened(item)
            open_file(item["path"])
        else:
            QMessageBox.information(
                self,
                "🎲 Modo Aleatório",
                "Nenhum arquivo encontrado para sorteio.\nVerifique se as pastas estão configuradas ou clique com o botão direito no botão Aleatório para configurar."
            )

    def _on_random_media_opened(self, file_data: dict):
        """Atualiza a interface destacando o item sorteado."""
        self.lbl_status_results.setText(f"🎲 Sorteado: {file_data.get('name', '')}")
        self.preview_panel.set_file_data(file_data)

    def _open_tv_mode(self):
        """Abre a janela dedicada do Modo TV como tela independente (não minimiza com o buscador)."""
        if self.worker and self.worker.isRunning():
            stats = self.db.get_stats()
            total_videos = stats.get("categories", {}).get("video", 0)

            if total_videos == 0:
                QMessageBox.information(
                    self,
                    "📺 Modo TV — Indexando Mídias",
                    "A indexação inicial de arquivos está em andamento e seus vídeos ainda estão sendo catalogados.\n\n"
                    "Por favor, aguarde a conclusão da varredura para sintonizar os canais de TV."
                )
                return

            reply = QMessageBox.question(
                self,
                "📺 Modo TV — Indexação em Andamento",
                "A indexação de arquivos ou o cálculo de durações ainda estão em andamento em segundo plano.\n\n"
                "A grade de programação pode conter estimativas temporárias até que a varredura seja concluída.\n\n"
                "Deseja abrir o Modo TV mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if self.tv_window is None or not self.tv_window.isVisible():
            self.tv_window = TVModeWindow(self.db, self.config, None)
            if hasattr(self, 'app_icon'):
                self.tv_window.setWindowIcon(self.app_icon)
            self.tv_window.show()
        else:
            self.tv_window.setWindowState(self.tv_window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
            self.tv_window.raise_()
            self.tv_window.activateWindow()

    def closeEvent(self, event):
        """Salva dimensões e estado ao fechar."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1000)

        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())
        self.config.set("window_maximized", self.isMaximized())
        self.config.set("preview_visible", self.preview_panel.isVisible())
        super().closeEvent(event)
