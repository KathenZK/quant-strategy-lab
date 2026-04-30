from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import aiohttp
import pandas as pd

from strategy_lab.data.liquidations import BinanceLiquidationStreamConfig, normalize_binance_force_order_events


@dataclass(slots=True)
class BinanceLiquidationStreamCollector:
    config: BinanceLiquidationStreamConfig = BinanceLiquidationStreamConfig()

    async def collect(
        self,
        *,
        duration_seconds: float | None = None,
        max_events: int | None = None,
    ) -> pd.DataFrame:
        url = f"{self.config.websocket_url}/{self.config.stream}"
        messages: list[dict[str, Any]] = []
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=None)
        start = asyncio.get_running_loop().time()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(url, heartbeat=30) as websocket:
                while True:
                    if duration_seconds is not None and (asyncio.get_running_loop().time() - start) >= duration_seconds:
                        break
                    if max_events is not None and len(messages) >= max_events:
                        break

                    message = await websocket.receive()
                    if message.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(message.data)
                        messages.append(payload)
                    elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR}:
                        break

        frames = [normalize_binance_force_order_events(message) for message in messages]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)
