"""Candles — the column-oriented OHLCV value type shared by klines/indicators.

Keeping one small column-oriented type (rather than passing raw exchange arrays
around) decouples the indicator logic from the exchange wire format and makes it
unit-testable without an exchange. ``from_klines`` parses the Binance USDⓈ-M
``/fapi/v1/klines`` shape; everything downstream reads ``.closes`` etc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Candles:
    times: list[int]      # bar open time (ms), oldest-first
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]

    def __len__(self) -> int:
        return len(self.closes)

    @property
    def last_close(self) -> float | None:
        return self.closes[-1] if self.closes else None

    @classmethod
    def from_klines(cls, raw: list[list]) -> "Candles":
        """Parse Binance USDⓈ-M klines: ``[openTime, o, h, l, c, v, ...]`` (strings)."""
        times, opens, highs, lows, closes, vols = [], [], [], [], [], []
        for k in raw:
            times.append(int(k[0]))
            opens.append(float(k[1]))
            highs.append(float(k[2]))
            lows.append(float(k[3]))
            closes.append(float(k[4]))
            vols.append(float(k[5]))
        return cls(times, opens, highs, lows, closes, vols)

    def to_rows(self) -> list[list]:
        """Render as ``[[ts,o,h,l,c,v]...]`` for the /market endpoint."""
        return [
            [self.times[i], self.opens[i], self.highs[i], self.lows[i], self.closes[i], self.volumes[i]]
            for i in range(len(self))
        ]
