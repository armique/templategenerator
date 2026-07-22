"""Visual tokens for the default dark theme."""

DARK_STYLESHEET = """
QWidget {
    background-color: #101318;
    color: #e6eaf0;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
}
QMainWindow {
    background-color: #101318;
}
QFrame#sidebar {
    background-color: #151a21;
    border-right: 1px solid #252c36;
}
QLabel#brand {
    color: #f4f7fb;
    font-size: 20px;
    font-weight: 700;
}
QLabel#eyebrow {
    color: #7f8b9b;
    font-size: 11px;
    font-weight: 600;
}
QLabel#pageTitle {
    color: #f4f7fb;
    font-size: 28px;
    font-weight: 650;
}
QLabel#emptyTitle {
    color: #f4f7fb;
    font-size: 18px;
    font-weight: 600;
}
QLabel#muted {
    color: #8e99a8;
}
QLineEdit {
    min-height: 42px;
    padding: 0 14px;
    background-color: #191f27;
    border: 1px solid #303947;
    border-radius: 8px;
    selection-background-color: #477bff;
}
QLineEdit:focus {
    border-color: #5b86ff;
}
QLineEdit:disabled {
    color: #6f7884;
    background-color: #151a20;
}
QPushButton {
    min-height: 42px;
    padding: 0 20px;
    color: #ffffff;
    background-color: #4775ed;
    border: 0;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #5683f4;
}
QPushButton:pressed {
    background-color: #3a66d2;
}
QPushButton:disabled {
    color: #7a8390;
    background-color: #282f39;
}
QFrame#emptyState {
    background-color: #151a21;
    border: 1px solid #252c36;
    border-radius: 12px;
}
QTableView {
    background-color: #151a21;
    alternate-background-color: #181e26;
    border: 1px solid #252c36;
    border-radius: 10px;
    gridline-color: #252c36;
    selection-background-color: #274b9f;
}
QHeaderView::section {
    color: #9ba6b5;
    background-color: #191f27;
    border: 0;
    border-bottom: 1px solid #303947;
    padding: 10px 8px;
    font-weight: 600;
}
QListWidget#recentSearches {
    color: #aeb7c4;
    background: transparent;
    border: 0;
    outline: 0;
}
QListWidget#recentSearches::item {
    padding: 6px 2px;
}
QListWidget#recentSearches::item:selected {
    color: #ffffff;
    background-color: #263249;
    border-radius: 4px;
}
QStatusBar {
    color: #8994a3;
    background-color: #101318;
    border-top: 1px solid #252c36;
}
"""

__all__ = ["DARK_STYLESHEET"]
