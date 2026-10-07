"""Windows 95 look and feel."""

RETRO_MENU_QSS = """
QMenu {
    background: #C0C0C0;
    color: #000000;
    font-family: "MS Sans Serif", "Tahoma";
    font-size: 8pt;
    border-top: 2px solid #FFFFFF;
    border-left: 2px solid #FFFFFF;
    border-right: 2px solid #404040;
    border-bottom: 2px solid #404040;
    padding: 2px;
}
QMenu::item {
    padding: 3px 20px 3px 22px;
}
QMenu::item:selected {
    background: #000080;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #808080;
}
QMenu::separator {
    height: 2px;
    margin: 3px 2px;
    border-top: 1px solid #808080;
    border-bottom: 1px solid #FFFFFF;
}
"""

# Win95 trackbar slider: sunken groove and a raised thumb.
RETRO_SLIDER_QSS = """
QWidget#chaosBox {
    background: #C0C0C0;
}
QLabel {
    color: #000000;
    font-family: "MS Sans Serif", "Tahoma";
    font-size: 8pt;
}
QLabel#chaosValue {
    color: #000080;
    font-weight: bold;
}
QSlider::groove:horizontal {
    height: 2px;
    background: #FFFFFF;
    border-top: 1px solid #808080;
    border-left: 1px solid #808080;
    border-bottom: 1px solid #FFFFFF;
    border-right: 1px solid #FFFFFF;
}
QSlider::handle:horizontal {
    width: 10px;
    margin: -9px 0;
    background: #C0C0C0;
    border-top: 1px solid #FFFFFF;
    border-left: 1px solid #FFFFFF;
    border-right: 2px solid #000000;
    border-bottom: 2px solid #000000;
}
"""
