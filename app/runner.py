# Copyright (c) 2020, Alexey Sokolov  <idales2020@outlook.com>
# Creative Commons BY-NC-SA 4.0 International Public License
# (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import asyncio
from asyncio import Task
from datetime import datetime
import importlib
import logging
import sys
from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, NamedTuple, Optional, Type, Union

import aiohttp
from pytimeparse.timeparse import timeparse

from app.database.common import DBException
import app.database.sqlite_provider as sqlite_db
from app.filetime import HUNDREDS_OF_NANOSECONDS, dt_to_filetime
from app.protocols import DBProviderProtocol, PluginProtocol

logger = logging.getLogger(__name__)


class Response(NamedTuple):
    status: int
    text: str


def interval_round(x: int, base: int) -> int:
    return x // base * base


EPS_ft = 10 * HUNDREDS_OF_NANOSECONDS // 1000  # 10 msec


def seconds_to_ft(seconds: Union[int, float]) -> int:
    return int(seconds * HUNDREDS_OF_NANOSECONDS)


def ft_to_seconds(ft: int) -> float:
    return ft / HUNDREDS_OF_NANOSECONDS


def make_db_provider(config: Dict[str, Any]) -> DBProviderProtocol:
    return sqlite_db.DBProvider(config)


def make_table_creation_method(
        plugin: PluginProtocol) -> Callable[[str], Awaitable[int]]:
    return plugin.create_sql_table_if_not_exists


class Runner:
    agent: str = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        def load_site_plugin(name: str) -> PluginProtocol:
            module = importlib.import_module(f'app.siteplugins.{name}')
            # dynamic loading from siteplugins folder
            return module.Siteplugin(self.db_provider)  # type: ignore

        self.config = config
        self.current_task: Optional[Task[Any]] = None

        self.db_provider = make_db_provider(config=config)
        sources = self.config.get('sources', None)
        plugins_list = set([source['type'] for source in sources])
        self.plugins = {name: load_site_plugin(name) for name in plugins_list}
        for source in sources:
            source['create_table'] = make_table_creation_method(
                self.plugins[source['type']])

    def __enter__(self) -> 'Runner':
        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(self._loop()))
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> None:
        asyncio.ensure_future(self._close())

    async def _loop(self) -> None:
        self.current_task = Task.current_task()
        timeout = 0.0
        try:
            sources = self.config.get('sources', None)
            while sources:
                async with self.db_provider:
                    utcnow_dt = datetime.utcnow()
                    utcnow_ft = dt_to_filetime(utcnow_dt)
                    timeouts = []
                    for source in sources:
                        timeouts.append(await
                                        self._check_request(source, utcnow_ft))
                    timeout = min(timeouts)
                    logger.info(f'next request after {timeout} sec')
                    await asyncio.sleep(timeout)

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error('Runner loop unhandled exception', exc_info=True)
            sys.exit(-1)

    async def _check_request(self, source: Dict, utcnow_ft: int) -> float:
        interval_ft: int = int(
            seconds_to_ft(timeparse(source['request_interval'])))
        last_request_time = source.get('last_request_time', None)
        if last_request_time is None or last_request_time // interval_ft != utcnow_ft // interval_ft:
            # make request
            url = source['url']
            try:
                try:
                    response = await Runner._make_request(url)
                    request_id = await self.db_provider.write_request(
                        source['id'], utcnow_ft, response.status)
                    await self._parse_response(response, request_id, source)
                except aiohttp.ClientError as err:
                    out_string = f"aiohttp.ClientError {type(err)} message {str(err)} on {url}"
                    logger.error(out_string)
                    self.db_provider.write_request(source['id'],
                                                   utcnow_ft,
                                                   0,
                                                   error=out_string)
            except DBException as e:
                logger.error(f'Database exception: {str(e)}')

            source['last_request_time'] = utcnow_ft
        timeout = interval_round(utcnow_ft + interval_ft,
                                 base=interval_ft) - utcnow_ft + EPS_ft
        return ft_to_seconds(timeout)

    @staticmethod
    async def _make_request(url: str) -> Response:
        async with aiohttp.ClientSession(
                headers={'User-Agent': Runner.agent}) as session:
            async with session.get(url) as response:
                return Response(status=response.status,
                                text=await response.text())

    async def _parse_response(self, response: Response, request_id: int,
                              source: Dict[str, Any]) -> None:
        if response.status == 200:
            await self.plugins[source['type']].parse(response.text, request_id,
                                                     source['table_name'])
        else:
            logger.error(f'Wrong status {response.status}')

    async def _close(self) -> None:
        assert (self.current_task is not None)
        self.current_task.cancel()
        await self.current_task
