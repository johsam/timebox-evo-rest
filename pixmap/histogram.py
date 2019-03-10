from typing import List, Dict, Union
from enum import Enum


class HistChange(Enum):
    no_change = 0
    min_changed = 1
    max_changed = 2
    value_changed = 3


class Histogram():
    def __init__(self, size: int, amplitude: int):
        self._size = size
        self._amp = amplitude
        self._value = {'value': 0, 'stamp': 0}  # type: Dict[str, Union[float, int]]
        self._min = {'value': 100.0, 'stamp': 0}  # type: Dict[str, Union[float, int]]
        self._max = {'value': -100.0, 'stamp': 0}  # type: Dict[str, Union[float, int]]
        self._points = []  # type: List[float]

    def width(self) -> int:
        return self._size

    def height(self) -> int:
        return self._amp

    def add(self, val: float, epoch: int) -> HistChange:
        result = HistChange.no_change

        if val < self._min['value']:
            self._min['value'] = val
            self._min['stamp'] = epoch
            result = HistChange.min_changed

        if val > self._max['value']:
            self._max['value'] = val
            self._max['stamp'] = epoch
            result = HistChange.max_changed

        if self._points and val == self._points[-1]:
            self._value['stamp'] = epoch
            return result

        self._points.append(val)
        self._value['value'] = val
        self._value['stamp'] = epoch

        if len(self._points) > self._size:
            self._points.pop(0)

        if result == HistChange.no_change:
            result = HistChange.value_changed

        return result

    def current(self) -> Dict[str, Union[float, int]]:
        return self._value

    def min(self) -> Dict[str, Union[float, int]]:
        return self._min

    def max(self) -> Dict[str, Union[float, int]]:
        return self._max

    def points(self) -> List:
        ret = []

        if self._points:
            mn, mx = min(self._points), max(self._points)
            extent = mx - mn
            if extent < 0.5:
                extent = 0.5

            for _, v in enumerate(self._points):
                amp = round((v - mn) * self._amp / extent) if extent != 0 else 0
                ret.append((v, amp))
        return ret
