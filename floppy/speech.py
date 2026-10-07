"""Floppy's lines and a speech bubble styled like a Windows 95 tooltip."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

TYPE_SPEED = 32.0           # characters per second
READ_TIME = 1.6             # how long the bubble stays after typing, plus...
READ_PER_CHAR = 0.05        # ...reading time per character

LINES: dict[str, tuple[str, ...]] = {
    "grab": ("Hey! Put me back!", "Whoa! Mind my sectors!", "Too high!",
             "Not into the drive!", "Hands off! I'm magnetic!"),
    "caught": ("Caught me! My hero.", "Phew, thanks!", "Nice catch!"),
    "held_long": ("Well? Gonna hold me all day?", "It's boring up here.", "I'm not a USB stick!"),
    "fast_drag": ("Aaaaaah!", "Slow down!", "I'm getting motion sick!"),
    "shake": ("Stop shaking! My sectors!", "Aaah, defragmentation!", "Quit it, my FAT is scrambled!"),
    "throw": ("Wheeee!", "I'm flyyying!", "Without a parachute?!"),
    "land_hard": ("Ouch! Bad sector!", "Oof... CRC error.", "That hurt!"),
    "land_fun": ("Again! Again!", "Let's do that again!", "Ten out of ten!"),
    "land_window": ("Great view from up here!", "I'm on a window! I'm the king!"),
    "dizzy": ("Where am I? Which drive is this?", "Everything's spinning...", "So many disk drives..."),
    "annoyed": ("That's it, I'm offended.", "Stop throwing me!", "I'll remember this. I have 1.44 MB of memory!"),
    "chute": ("Good thing I packed a parachute.", "Nice and easy..."),
    "window_gone": ("Hey! I was standing there!", "Who moved my window?!"),
    "mischief": ("Hee hee.", "Check this out!", "Oops.", "Wasn't me."),
    "panic": ("Ha! Panic!", "Correct choice."),
    "tug": ("Not letting go!", "Hnnng... heavy!", "Not one step back!"),
    "tug_tired": ("Pfff... fine, take it.", "I'm tired. You win."),
    "tug_win": ("Hehe, mine!", "Victory!"),
    "wake": ("Huh? What? I'm not asleep!", "Five more minutes..."),
    "rage_warn": ("Stop it!", "One more click and it's a blue screen!"),
    "forgiven": ("Thanks for forgiving me!",),
    "boss": ("Shh... I'll be quiet.",),
    "apology_ok": ("Fine, you're forgiven.",),
    "apology_no": ("Just try it!",),
    "hug": ("Hugs!", "Aww, nice!", "Careful, I'm fragile!"),
    "handshake": ("I don't have hands, but thanks!", "Firm handshake!"),
    "thanked": ("You're welcome!", "Anytime!"),
    "unthanked": ("Fine then!", "Hmph."),
    "sneak": ("Shh...", "Tiptoe, tiptoe...", "It's not moving... Is it asleep?"),
    "scared": ("EEK!", "IT'S ALIVE!", "Aaah! The mouse!", "Don't do that!"),
    # Hauling a video in from behind the screen.
    "haul_reach": ("Hold on, I left something back here...", "It's somewhere behind the screen...",
                   "Ooh, what's this?", "Found something! Heavy..."),
    "haul_pull": ("Hnnnng!", "Heave... HO!", "Help me pull! No? Fine."),
    "haul_done": ("Showtime!", "Enjoy the show!", "Popcorn not included.", "You're welcome."),
    "haul_lost": ("Hey, I was carrying that!", "Fine, you hold it then."),
    "haul_fail": ("Nope, nothing back there.", "The internet is out. Classic."),
    # Graffiti.
    "graffiti_start": ("Psst. Don't tell anyone.", "Time for some art!", "Shake, shake, shake..."),
    "graffiti_done": ("Masterpiece.", "Signed and sealed.", "Banksy who?"),
    "graffiti_wiped": ("Hey! That was art!", "Vandal! Oh wait.", "My masterpiece!"),
    # The clone.
    "clone_copy": ("Ctrl+C...", "Selecting myself... Ctrl+C..."),
    "clone_paste": ("...Ctrl+V!", "...and paste!"),
    "clone_argue": ("Hey! I'm the original!", "There can be only one!", "Who are you calling a copy?!"),
    "clone_bin": ("To the Recycle Bin with you!", "Drag and drop!", "Delete!"),
    "clone_binned": ("Copy of Floppy was moved to the Recycle Bin.", "Don't empty it. Or do."),
    "clone_deleted": ("Thanks! He was a cheap copy anyway.", "Shift+Delete. Brutal. I like it."),
    # Minesweeper.
    "blast": ("KABOOM!", "MINE!", "Wasn't a number!"),
    "blast_land": ("I'm fine! Totally fine!", "That was a 3, not a 2...", "Who put a mine there?!"),
    "blast_far": ("Did you hear a boom?", "Someone stepped on a mine."),
    "mines_floppy_won": ("Too easy.", "Minesweeper champion of drive A:!"),
    "mines_user_won": ("You cheated!", "Beginner's luck.", "Teach me!"),
    "mines_taken": ("Fine, you play.", "Show me how it's done, then."),
    # The defragmenter.
    "defrag_oops": ("Ah... ACHOO! Oops.", "Bless me. Sorry about your disk."),
    "defrag_stop": ("Hey! I was almost done!", "Fine. Stay fragmented."),
}


class SpeechBubble(QWidget):
    """A rectangular yellow Win95 tooltip with a pixel tail pointing at Floppy."""

    MAX_W = 200
    PAD = 6
    TAIL = 8

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,  # clicks pass straight through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._font = QFont("Tahoma")
        self._font.setPixelSize(12)
        self._text = ""
        self._shown = ""
        self._box = QRectF()
        self._tail_x = 0.0

    def show_text(self, text: str, visible: int, anchor: QPointF) -> None:
        """anchor is the point above Floppy's head that the tail points to."""
        if text != self._text:
            self._text = text
            self._layout_box()
        self._shown = text[:visible]
        w, h = int(self._box.width()) + 4, int(self._box.height()) + self.TAIL + 4
        if self.size().width() != w or self.size().height() != h:
            self.setFixedSize(w, h)

        avail = (QGuiApplication.screenAt(anchor.toPoint()) or QGuiApplication.primaryScreen()).availableGeometry()
        x = anchor.x() - w / 2
        x = max(avail.left() + 2, min(x, avail.right() - w - 2))
        y = max(avail.top() + 2, anchor.y() - h)
        self._tail_x = max(10.0, min(anchor.x() - x, w - 14.0))
        self.move(round(x), round(y))
        if not self.isVisible():
            self.show()
        self.update()

    def _layout_box(self) -> None:
        fm = QFontMetricsF(self._font)
        rect = fm.boundingRect(QRectF(0, 0, self.MAX_W - 2 * self.PAD, 1000),
                               Qt.TextFlag.TextWordWrap, self._text)
        self._box = QRectF(0, 0, rect.width() + 2 * self.PAD + 2, rect.height() + 2 * self.PAD)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        box = self._box.translated(1, 1)

        # Hard drop shadow, like Win95 windows.
        p.fillRect(box.translated(2, 2), QColor(0, 0, 0, 110))
        p.fillRect(box, QColor("#FFFFE1"))

        tail = QPainterPath()
        tx, ty = box.left() + self._tail_x, box.bottom()
        tail.moveTo(tx - 6, ty - 1)
        tail.lineTo(tx + 4, ty - 1)
        tail.lineTo(tx - 2, ty + self.TAIL)
        tail.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFE1"))
        p.drawPath(tail)

        p.setPen(QPen(QColor("#000000"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(box.left(), box.top()), QPointF(box.right(), box.top()))
        p.drawLine(QPointF(box.left(), box.top()), QPointF(box.left(), box.bottom()))
        p.drawLine(QPointF(box.right(), box.top()), QPointF(box.right(), box.bottom()))
        p.drawLine(QPointF(box.left(), box.bottom()), QPointF(tx - 6, box.bottom()))
        p.drawLine(QPointF(tx + 4, box.bottom()), QPointF(box.right(), box.bottom()))
        p.drawLine(QPointF(tx - 6, ty), QPointF(tx - 2, ty + self.TAIL))
        p.drawLine(QPointF(tx + 4, ty), QPointF(tx - 2, ty + self.TAIL))

        p.setFont(self._font)
        p.setPen(QColor("#000000"))
        p.drawText(box.adjusted(self.PAD, self.PAD, -self.PAD, -self.PAD),
                   Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft, self._shown)
        p.end()
