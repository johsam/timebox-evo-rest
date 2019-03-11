import time
import logging

from enum import Enum
from typing import Any
from pixmap.rawpixmap import RawPixmap, RGBColor
from pixmap.histogram import Histogram, HistChange


class TempType(Enum):
    val = 0
    min_val = 1
    max_val = 2


class ModeType(Enum):
    hist = 0
    clock = 1
    min = 2
    max = 3
    image = 4


class HistPixmap(RawPixmap):

    def __init__(self, width: int, height: int, divoom: Any):
        super().__init__(width, height)
        self._histogram = Histogram(width - 2, 5)
        self._mode = ModeType.hist  # type: ModeType
        self._divoom = divoom

    @classmethod
    def _toChar(cls, val) -> str:
        return chr(int(val) + ord('0'))

    @classmethod
    def _format_temp(cls, val: float) -> str:
        return "{:.1f}".format(round(float(val), 1))

    def set_mode(self, mode: ModeType):
        self._mode = ModeType(mode)
        self.draw_mode(self._mode)
        logging.info('Mode {} selected'.format(self._mode))

    def draw_mode(self, mode: ModeType):
        self.clear()
        logging.info('Draw mode {}'.format(mode))

        if mode == ModeType.hist:
            current = self._histogram.current()
            self.draw_temp(current['value'])
            self.draw_histogram()

        if mode == ModeType.clock:
            current = self._histogram.current()
            self.draw_temp(current['value'])
            self.draw_clock(int(current['stamp']))

        if mode == ModeType.min:
            current = self._histogram.min()
            self.draw_temp(current['value'])
            self.draw_min_arrow(current['value'])
            self.draw_clock(int(current['stamp']))

        if mode == ModeType.max:
            current = self._histogram.max()
            self.draw_temp(current['value'])
            self.draw_max_arrow(current['value'])
            self.draw_clock(int(current['stamp']))

        if mode == ModeType.image:
            self.display_image()

        self._divoom.send()

    def load_image(self, path: str):
        if super(HistPixmap, self).load_image(path):
            super(HistPixmap, self).display_image()

            self._divoom.send()

    def reset_min_max(self):
        self._histogram.reset_min_max()
        self.draw_mode(self._mode)

    def add_temp(self, val: float, epoch: int):

        val = float(self._format_temp(val))
        change = self._histogram.add(val, epoch)

        logging.info('New temp {} added, status={}'.format(val, change))

        if change == HistChange.min_changed:
            self.draw_mode(ModeType.min)
            self._divoom.after_delay(2, lambda: self.draw_mode(self._mode))

        if change == HistChange.max_changed:
            self.draw_mode(ModeType.max)
            self._divoom.after_delay(2, lambda: self.draw_mode(self._mode))

        if change == HistChange.no_change:
            self.draw_mode(self._mode)

        if change == HistChange.value_changed:
            self.draw_mode(self._mode)

    def draw_clock(self, epoch: int):
        t = time.localtime(epoch)

        tens = t.tm_hour / 10
        ones = t.tm_hour % 10

        self.smallCharAt(HistPixmap._toChar(tens), 0, 10, RawPixmap.WHITE)
        self.smallCharAt(HistPixmap._toChar(ones), 4, 10, RawPixmap.WHITE)

        tens = t.tm_min / 10
        ones = t.tm_min % 10

        self.smallCharAt(HistPixmap._toChar(tens), 9, 10, RawPixmap.WHITE)
        self.smallCharAt(HistPixmap._toChar(ones), 13, 10, RawPixmap.WHITE)

    def draw_histogram(self):
        hh = self._histogram.height()

        self.line(0, self._height - hh - 2, 0, self._height - 1, RawPixmap.WHITE)
        self.line(0, self._height - 1, self._width - 1, self._height - 1, RawPixmap.WHITE)
        self.line(self._width - 1, self._height - hh - 2, self._width - 1, self._height - 1, RawPixmap.WHITE)

        for i, v in enumerate(reversed(self._histogram.points())):
            (val, amp) = v
            if val < 0:
                self.setPixel(self._width - 2 - i, self._height - 2 - amp, RawPixmap.DEG_MINUS)
            else:
                self.setPixel(self._width - 2 - i, self._height - 2 - amp, RawPixmap.DEG_PLUS)

    def draw_min_arrow(self, val: float):
        color = self.temp_color(val)
        self.line(1, 1, 1, 5, color)

    def draw_max_arrow(self, val: float):
        color = self.temp_color(val)
        self.line(1, 7, 1, 3, color)

    def temp_color(self, val: float) -> RGBColor:
        color = RawPixmap.DEG_MINUS
        if val >= 0.0:
            color = RawPixmap.DEG_PLUS
        return color

    def draw_temp(self, val: float):
        # Pick color
        color = self.temp_color(val)

        # Draw sign
        if val >= 0.0:
            self.smallCharAt('+', 0, 2, color)
        else:
            self.smallCharAt('-', 0, 2, color)

        # Draw the value
        if -10.0 < val < 10.0:  # if val > -10.0 and val < 10.0:
            deg = abs(val)
            decimal = (abs(val) * 10) % 10

            self.charAt(HistPixmap._toChar(deg), 4, 1, color)

            # Decimal point
            self.setPixel(10, 7, color)

            # Decimal value
            self.smallCharAt(HistPixmap._toChar(decimal), 12, 3, color)

        else:
            tens = abs(val) / 10
            ones = abs(val) % 10

            self.charAt(HistPixmap._toChar(tens), 4, 1, color)
            self.charAt(HistPixmap._toChar(ones), 10, 1, color)
