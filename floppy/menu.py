"""Retro right-click menu."""

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QSlider, QVBoxLayout, QWidget, QWidgetAction

from .config import CHAOS_LEVELS, PRANKS
from .skins import SKINS
from .theme import RETRO_MENU_QSS, RETRO_SLIDER_QSS


def _chaos_caption(index: int) -> str:
    level = CHAOS_LEVELS[index]
    return f"{level.title}, {level.percent}%" if level.percent else level.title


def _slider_action(menu: QMenu, title: str, caption: Callable[[int], str], maximum: int,
                   value: int, on_change: Callable[[int], None], step: int = 1) -> QWidgetAction:
    """A Win95 trackbar with a live caption, embedded in the menu."""
    box = QWidget()
    box.setObjectName("chaosBox")
    box.setStyleSheet(RETRO_SLIDER_QSS)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(22, 6, 16, 6)
    layout.setSpacing(4)

    header = QHBoxLayout()
    header.addWidget(QLabel(title))
    label = QLabel(caption(value))
    label.setObjectName("chaosValue")
    header.addWidget(label)
    header.addStretch()
    layout.addLayout(header)

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, maximum)
    slider.setSingleStep(step)
    slider.setPageStep(step)
    slider.setValue(value)
    slider.setMinimumWidth(170)
    slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    layout.addWidget(slider)

    def changed(v: int) -> None:
        label.setText(caption(v))
        on_change(v)

    slider.valueChanged.connect(changed)
    action = QWidgetAction(menu)
    action.setDefaultWidget(box)
    return action


def build_menu(
    parent: QWidget,
    *,
    chaos_index: int,
    skin_key: str,
    asleep: bool,
    sound_enabled: bool,
    volume: int,
    enabled_pranks: set[str],
    youtube: bool,
    on_chaos: Callable[[int], None],
    on_skin: Callable[[str], None],
    on_sleep: Callable[[], None],
    on_wake: Callable[[], None],
    on_performance: Callable[[str | None], None],
    on_prank_toggle: Callable[[str, bool], None],
    on_youtube: Callable[[bool], None],
    on_edit_videos: Callable[[], None],
    on_sound_toggle: Callable[[bool], None],
    on_volume: Callable[[int], None],
    on_eject: Callable[[], None],
) -> QMenu:
    menu = QMenu(parent)
    menu.setStyleSheet(RETRO_MENU_QSS)

    menu.addAction(_slider_action(menu, "Chaos level:", _chaos_caption, len(CHAOS_LEVELS) - 1,
                                  chaos_index, on_chaos))
    menu.addSeparator()

    skins_menu = menu.addMenu("Floppy skin")
    skins_menu.setStyleSheet(RETRO_MENU_QSS)
    group = QActionGroup(skins_menu)
    for skin in SKINS.values():
        action = QAction(skin.title, skins_menu, checkable=True)
        action.setChecked(skin.key == skin_key)
        action.triggered.connect(lambda _=False, key=skin.key: on_skin(key))
        group.addAction(action)
        skins_menu.addAction(action)

    sound_menu = menu.addMenu("Sound")
    sound_menu.setStyleSheet(RETRO_MENU_QSS)
    toggle = QAction("Sound effects", sound_menu, checkable=True)
    toggle.setChecked(sound_enabled)
    toggle.toggled.connect(on_sound_toggle)
    sound_menu.addAction(toggle)
    sound_menu.addAction(_slider_action(sound_menu, "Volume:", lambda v: f"{v}%", 100, volume,
                                        on_volume, step=5))

    pranks_menu = menu.addMenu("Pranks")
    pranks_menu.setStyleSheet(RETRO_MENU_QSS)
    for kind, (title, _weight, _floor) in PRANKS.items():
        action = QAction(title, pranks_menu, checkable=True)
        action.setChecked(kind in enabled_pranks)
        action.toggled.connect(lambda on, k=kind: on_prank_toggle(k, on))
        pranks_menu.addAction(action)
    pranks_menu.addSeparator()
    yt = QAction("Real YouTube videos", pranks_menu, checkable=True)
    yt.setChecked(youtube)
    yt.toggled.connect(on_youtube)
    pranks_menu.addAction(yt)
    pranks_menu.addAction("Edit video list...", on_edit_videos)

    if asleep:
        menu.addAction("Wake up", on_wake)
    else:
        menu.addAction("Sleep for 15 minutes", on_sleep)
    show_menu = menu.addMenu("Put on a show")
    show_menu.setStyleSheet(RETRO_MENU_QSS)
    show_menu.addAction("Surprise me!", lambda: on_performance(None))
    show_menu.addSeparator()
    for kind, (title, _weight, _floor) in PRANKS.items():
        show_menu.addAction(title, lambda k=kind: on_performance(k))
    show_menu.addAction("Blue screen", lambda: on_performance("bsod"))

    menu.addSeparator()
    menu.addAction("Eject floppy", on_eject)
    return menu
