# Folha de Estilos QSS moderna com tema escuro (Dark Theme)

DARK_THEME_QSS = """
/* Reset e Base */
QWidget {
    background-color: #121418;
    color: #E2E8F0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

/* Janela Principal */
QMainWindow {
    background-color: #0F1115;
}

/* Barra de Busca */
QLineEdit#search_input {
    background-color: #1E232B;
    border: 2px solid #2D3748;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 15px;
    color: #FFFFFF;
    selection-background-color: #3B82F6;
}
QLineEdit#search_input:focus {
    border: 2px solid #3B82F6;
    background-color: #242B35;
}

/* Botões Modernos */
QPushButton {
    background-color: #1E232B;
    color: #E2E8F0;
    border: 1px solid #2D3748;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2D3748;
    border-color: #4A5568;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #1A202C;
}

/* Botão Primário de Ação */
QPushButton#primary_action_btn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #3B82F6);
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#primary_action_btn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB);
}
QPushButton#primary_action_btn:pressed {
    background-color: #1E40AF;
}

/* Botão Modo Aleatório */
QPushButton#random_mode_btn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #9333EA);
    color: #FFFFFF;
    border: 1px solid #A855F7;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton#random_mode_btn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #7C3AED);
    border-color: #C084FC;
}
QPushButton#random_mode_btn:pressed {
    background-color: #581C87;
}

/* Botão Modo TV */
QPushButton#tv_mode_btn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #0EA5E9);
    color: #FFFFFF;
    border: 1px solid #38BDF8;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton#tv_mode_btn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #0284C7);
    border-color: #7DD3FC;
}
QPushButton#tv_mode_btn:pressed {
    background-color: #0C4A6E;
}

/* Botão Secundário de Ação (Explorer) */
QPushButton#explorer_action_btn {
    background-color: #1E293B;
    color: #38BDF8;
    border: 1px solid #0284C7;
    border-radius: 8px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#explorer_action_btn:hover {
    background-color: #0284C7;
    color: #FFFFFF;
}

/* Botão Transmitir para TV */
QPushButton#cast_action_btn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3A8A, stop:1 #2563EB);
    color: #FFFFFF;
    border: 1px solid #3B82F6;
    border-radius: 8px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#cast_action_btn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6);
    border-color: #60A5FA;
}
QPushButton#cast_action_btn:pressed {
    background-color: #172554;
}

/* Chips / Botões de Filtro */
QPushButton.filter_chip {
    background-color: #1A1F26;
    color: #94A3B8;
    border: 1px solid #2A323D;
    border-radius: 16px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton.filter_chip:hover {
    background-color: #242B35;
    color: #F1F5F9;
    border-color: #475569;
}
QPushButton.filter_chip[checked="true"] {
    background-color: #1D4ED8;
    color: #FFFFFF;
    border: 1px solid #3B82F6;
}

/* Combobox / Seletores */
QComboBox {
    background-color: #1E232B;
    border: 1px solid #2D3748;
    border-radius: 8px;
    padding: 6px 12px;
    color: #E2E8F0;
    min-width: 110px;
}
QComboBox:hover {
    border-color: #4A5568;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1A1F26;
    border: 1px solid #2D3748;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    color: #E2E8F0;
    padding: 4px;
}

/* Tabela de Resultados */
QTableWidget, QTableView {
    background-color: #15181E;
    border: 1px solid #242A34;
    border-radius: 10px;
    gridline-color: #1E232B;
    color: #CBD5E1;
    font-size: 13px;
}
QTableWidget::item, QTableView::item {
    padding: 6px 10px;
    border-bottom: 1px solid #1A1F27;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QTableWidget::item:hover:!selected, QTableView::item:hover:!selected {
    background-color: #1C222C;
}

/* Cabeçalho da Tabela - Sem cortes e com alinhamento perfeito */
QHeaderView {
    background-color: #181C23;
    border: none;
}
QHeaderView::section {
    background-color: #181C23;
    color: #94A3B8;
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid #2A323D;
    border-right: 1px solid #1F242D;
    font-weight: bold;
    font-size: 12px;
    text-align: left;
}
QHeaderView::section:hover {
    background-color: #1E242D;
    color: #38BDF8;
}

/* Tabela de Resultados */
QTableWidget, QTableView {
    background-color: #15181E;
    border: 1px solid #242A34;
    border-radius: 10px;
    gridline-color: #1A1F27;
    color: #CBD5E1;
    font-size: 13px;
    outline: none;
}
QTableWidget::item, QTableView::item {
    padding: 6px 10px;
    border-bottom: 1px solid #181D24;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QTableWidget::item:hover:!selected, QTableView::item:hover:!selected {
    background-color: #1C232E;
}

/* Painel de Preview Lateral */
QFrame#preview_panel {
    background-color: #161A21;
    border: 1px solid #242A34;
    border-radius: 12px;
}

QFrame#preview_img_container {
    background-color: #0E1014;
    border: 1px solid #1E242D;
    border-radius: 8px;
}

QTextEdit#preview_text_view {
    background-color: #0E1014;
    color: #94A3B8;
    border: 1px solid #1E242D;
    border-radius: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 8px;
}


/* Scrollbars Modernas */
QScrollBar:vertical {
    background: #121418;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2D3748;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #4A5568;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #121418;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #2D3748;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #4A5568;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Barra de Status */
QStatusBar {
    background-color: #0E1014;
    color: #94A3B8;
    font-size: 12px;
    border-top: 1px solid #1E232B;
}

/* Menu de Contexto (Botão Direito) */
QMenu {
    background-color: #1A1F26;
    color: #E2E8F0;
    border: 1px solid #2D3748;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background-color: #2D3748;
    margin: 4px 6px;
}

/* Diálogos */
QDialog {
    background-color: #121418;
}

QListWidget {
    background-color: #15181E;
    border: 1px solid #242A34;
    border-radius: 8px;
    padding: 6px;
    color: #E2E8F0;
}
QListWidget::item {
    padding: 8px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
QListWidget::item:hover:!selected {
    background-color: #1E232B;
}

/* Barra de Progresso */
QProgressBar {
    background-color: #1E232B;
    border: 1px solid #2D3748;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #38BDF8);
    border-radius: 5px;
}
"""
