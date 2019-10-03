import time
import logging

from enum import Enum
from typing import Any, Union, List
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
    sunrise = 5
    sunset = 6
    forecastmax = 7
    forecastmin = 8

    def __int__(self):
        return self.value

    def next(self):
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            index = 0
        return members[index]

    def prev(self):
        cls = self.__class__
        members = list(cls)
        index = members.index(self) - 1
        if index < 0:
            index = len(members) - 1
        return members[index]


class HistPixmap(RawPixmap):

    def __init__(self, width: int, height: int, divoom: Any):
        super().__init__(width, height)
        self._uploaded = [(0, 0, 0)] * width * height  # type: List[RGBColor]
        self._histogram = Histogram(width - 2, 5)
        self._mode = ModeType.hist  # type: ModeType
        self._divoom = divoom
        self._sunrise_epoch = 0
        self._sunset_epoch = 0

        self._forecast = {}  # type: dict

        self._width = width
        self._height = height

    @classmethod
    def _toChar(cls, val) -> str:
        return chr(int(val) + ord('0'))

    @classmethod
    def _format_temp(cls, val: float) -> str:
        return "{:.1f}".format(round(float(val), 1))

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def set_sunrise(self, epoch: int):
        self._sunrise_epoch = epoch
        self.draw_mode(self._mode)

    def set_sunset(self, epoch: int):
        self._sunset_epoch = epoch
        self.draw_mode(self._mode)

    def set_forecast(self, forecast: dict):
        self._forecast = forecast
        self.draw_mode(self._mode)

    def set_mode(self, mode: Union[int, str]):
        if isinstance(mode, int):
            self._mode = ModeType(mode)
        else:
            if mode == 'next':
                self._mode = self._mode.next()
            if mode == 'prev':
                self._mode = self._mode.prev()

        logging.info("Mode %s selected", self._mode)
        self.draw_mode(self._mode)

    def draw_mode(self, mode: ModeType, alt: bool = False):
        self.clear()
        logging.info("Drawing mode %s", mode)

        if mode == ModeType.hist:
            current = self._histogram.current()
            self.draw_temp(current['value'])
            self.draw_histogram()

        if mode == ModeType.clock:
            current = self._histogram.current()
            self.draw_temp(current['value'])
            self.draw_clock(int(current['stamp']), alt)

        if mode == ModeType.min:
            current = self._histogram.min()
            self.draw_temp(current['value'], alt)
            if not alt:
                self.draw_min_arrow(current['value'])
            self.draw_clock(int(current['stamp']))

        if mode == ModeType.max:
            current = self._histogram.max()
            self.draw_temp(current['value'], alt)
            if not alt:
                self.draw_max_arrow(current['value'])
            self.draw_clock(int(current['stamp']))

        if mode == ModeType.image:
            self.set_rgb_pixels(self._uploaded)

        if mode == ModeType.sunrise:
            img = super(HistPixmap, self).load_image('backgrounds/sunup.png')
            pixels = super(HistPixmap, self).decode_image(img)

            self.set_rgb_pixels(pixels)
            self.draw_clock(self._sunrise_epoch)

        if mode == ModeType.sunset:
            img = super(HistPixmap, self).load_image('backgrounds/sundown.png')
            pixels = super(HistPixmap, self).decode_image(img)

            self.set_rgb_pixels(pixels)
            self.draw_clock(self._sunset_epoch)

        if mode == ModeType.forecastmax:
            if 'max' not in self._forecast:
                return
            self.draw_forecast_symbol('max')
            self._divoom.send()
            time.sleep(1)
            self.draw_forecast('max')

        if mode == ModeType.forecastmin:
            if 'min' not in self._forecast:
                return

            self.draw_forecast_symbol('min')
            self._divoom.send()
            time.sleep(1)
            self.draw_forecast('min')

        self._divoom.send()

    def load_image(self, path: str):
        img = super(HistPixmap, self).load_image(path)
        pixels = super(HistPixmap, self).decode_image(img)

        self._uploaded = list(pixels)
        self.set_mode(int(ModeType.image))

    def reset_min_max(self):
        self._histogram.reset_min_max()
        self.draw_mode(self._mode)

    def add_temp(self, val: float, epoch: int):

        val = float(self._format_temp(val))
        change = self._histogram.add(val, epoch)

        logging.info("New temp %s added, status=%s", val, change)

        if change == HistChange.min_changed:
            self.draw_mode(ModeType.min)
            self._divoom.after_delay(1, lambda: self.draw_mode(ModeType.min, True))
            self._divoom.after_delay(2, lambda: self.draw_mode(ModeType.min))
            self._divoom.after_delay(3, lambda: self.draw_mode(ModeType.min, True))
            self._divoom.after_delay(4, lambda: self.draw_mode(ModeType.min))
            self._divoom.after_delay(5, lambda: self.draw_mode(self._mode))

        if change == HistChange.max_changed:
            self.draw_mode(ModeType.max)
            self._divoom.after_delay(1, lambda: self.draw_mode(ModeType.max, True))
            self._divoom.after_delay(2, lambda: self.draw_mode(ModeType.max))
            self._divoom.after_delay(3, lambda: self.draw_mode(ModeType.max, True))
            self._divoom.after_delay(4, lambda: self.draw_mode(ModeType.max))
            self._divoom.after_delay(5, lambda: self.draw_mode(self._mode))

        if change == HistChange.no_change:
            self.draw_mode(self._mode)

        if change == HistChange.value_changed:
            self.draw_mode(self._mode)
            self._divoom.after_delay(1, lambda: self.draw_mode(self._mode, True))
            self._divoom.after_delay(2, lambda: self.draw_mode(self._mode))

    def draw_clock(self, epoch: int, alt: bool = False):
        if not alt:
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

    def draw_temp(self, val: float, alt: bool = False):
        # Pick color
        color = self.temp_color(val)

        if not alt:
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
            tens = int(abs(val) / 10)
            ones = int(abs(val) % 10)

            self.charAt(HistPixmap._toChar(tens), 4, 1, color)
            self.charAt(HistPixmap._toChar(ones), 10, 1, color)

    def draw_forecast_symbol(self, min_or_max: str):
        img = super(HistPixmap, self).load_image('backgrounds/yr/{}.png'.format(self._forecast[min_or_max]['symbol']))
        pixels = super(HistPixmap, self).decode_image(img, False)
        self.set_rgb_pixels(pixels)

    def draw_forecast(self, min_or_max: str):
        img = super(HistPixmap, self).load_image('backgrounds/yr/{}.png'.format(self._forecast[min_or_max]['symbol']))
        pixels = super(HistPixmap, self).decode_image(img, True)
        self.set_rgb_pixels(pixels)
        self.draw_clock(self._forecast[min_or_max]['timestamp'])
        self.draw_forecast_temp(self._forecast[min_or_max]['temp'])
        self._divoom.send()

    def draw_forecast_temp(self, val: float):

        # Pick color
        color = self.temp_color(val)

        tens = int(abs(val) / 10)
        ones = int(abs(val) % 10)
        signpos = 4

        if tens == 0:
            signpos = 8
        else:
            self.smallCharAt(HistPixmap._toChar(tens), 8, 1, color)

        self.smallCharAt(HistPixmap._toChar(ones), 12, 1, color)

        if val >= 0.0:
            self.smallCharAt('+', signpos, 1, color)
        else:
            self.smallCharAt('-', signpos, 1, color)
