#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from collections import deque
from typing import NamedTuple

from qt.core import QDialog, QObject, QTextToSpeech, pyqtSignal

from calibre.gui2 import error_dialog


class Utterance(NamedTuple):
    text: str
    index_in_positions: int
    offset_in_text: int
    reached_offset: int = 0


class Position(NamedTuple):
    mark: int
    offset_in_text: int


class Tracker:

    def __init__(self):
        self.clear()

    def clear(self):
        self.positions: list[Position] = []
        self.last_pos = 0
        self.queue: deque[Utterance] = deque()

    def parse_marked_text(self, marked_text, limit = 32 * 1024):
        self.clear()
        text = []
        text_len = chunk_len = index_in_positions = offset_in_text = 0

        def commit():
            self.queue.append(Utterance(''.join(text), index_in_positions, offset_in_text))

        for x in marked_text:
            if isinstance(x, int):
                self.positions.append(Position(x, text_len))
            else:
                text_len += len(x)
                chunk_len += len(x)
                text.append(x)
                if chunk_len > limit:
                    commit()
                    chunk_len = 0
                    text = []
                    index_in_positions = max(0, len(self.positions) - 1)
                    offset_in_text = text_len
        if len(text):
            commit()
        self.marked_text = marked_text
        return self.current_text()

    def pop_first(self):
        if self.queue:
            self.queue.popleft()

    def current_text(self):
        if self.queue:
            return self.queue[0].text
        return ''

    def resume(self):
        self.last_pos = 0
        if self.queue:
            self.last_pos = self.queue[0].index_in_positions
            if self.queue[0].reached_offset:
                o = self.queue[0].reached_offset
                # make sure positions remain the same for word tracking
                self.queue[0].text = (' ' * o) + self.queue[0].text[o:]
        return self.current_text()

    def boundary_reached(self, start):
        if self.queue:
            self.queue[0] = self.queue[0]._replace(reached_offset=start)

    def mark_word_or_sentence(self, start, length):
        if not self.queue:
            return
        start += self.queue[0].offset_in_text
        end = start + length
        matches = []
        while self.last_pos < len(self.positions):
            pos = self.positions[self.last_pos]
            if start <= pos.offset_in_text < end:
                matches.append(pos)
            elif pos.offset_in_text >= end:
                break
            self.last_pos += 1
        if len(matches):
            return matches[0].mark, matches[-1].mark
        return None


class TTSManager(QObject):

    state_changed = pyqtSignal(QTextToSpeech.State)
    saying = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tts = None
        self.state = QTextToSpeech.State.Ready
        self.tracker = Tracker()

    @property
    def tts(self):
        if self._tts is None:
            from calibre.gui2.tts2.types import create_tts_backend
            self._tts = create_tts_backend(parent=self)
            self._tts.state_changed.connect(self._state_changed)
            self._tts.saying.connect(self._saying)
        return self._tts

    def stop(self) -> None:
        self.tracker.clear()
        self.tts.stop()

    def pause(self) -> None:
        self.tts.pause()

    def resume(self) -> None:
        self.tts.resume()

    def speak_simple_text(self, text: str) -> None:
        self.speak_marked_text([0, text])

    def speak_marked_text(self, marked_text):
        self.stop()
        self.tts.say(self.tracker.parse_marked_text(marked_text))

    def configure(self) -> None:
        from calibre.gui2.tts2.config import ConfigDialog
        self.tts.pause()
        d = ConfigDialog(parent=self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.stop()
            self._tts = None
        if self._tts is None:
            self.tts.say(self.tracker.resume())
        else:
            self.tts.resume()

    def _state_changed(self, state: QTextToSpeech.State) -> None:
        self.state = state
        if state is QTextToSpeech.State.Error:
            error_dialog(self, _('Read aloud failed'), self.tts.error_message(), show=True)
        self.state_changed.emit(state)

    def _saying(self, offset: int, length: int) -> None:
        self.tracker.boundary_reached(offset)
        x = self.tracker.mark_word_or_sentence(offset, length)
        if x is not None:
            self.saying.emit(x[0], x[1])
