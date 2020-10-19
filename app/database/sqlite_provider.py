# Copyright (c) 2020, Alexey Sokolov  <idales2020@outlook.com>
# Creative Commons BY-NC-SA 4.0 International Public License
# (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import asyncio
from datetime import datetime, timedelta
import logging
import sqlite3
import sys
from typing import Any, Dict, List, Optional

from pytimeparse.timeparse import timeparse

from app.database.common import DBException
from app.database.sqlite_db_scripts import DBScripts
from app.filetime import dt_to_filetime, filetime_to_dt
from app.protocols import DBProviderProtocol

logger = logging.getLogger(__name__)


class DBProvider(DBProviderProtocol):

    DATABASE_NAME = "requests_and_data.db"

    def __init__(self, config):
        self.config = config['database']
        self.sources = config['sources']
        self.current_task = None
        self.conn = None
        self.lock = asyncio.Lock()
        self.initialized_sources = asyncio.Event()

    @staticmethod
    def get_syntax() -> str:
        return 'sqlite'

    async def __aenter__(self):
        asyncio.ensure_future(self._loop())
        await self.initialized_sources.wait()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        asyncio.ensure_future(self._close())

    async def _loop(self):
        self.current_task = asyncio.Task.current_task()
        try:
            with await DBScripts.create_connection(DBProvider.DATABASE_NAME
                                                   ) as conn:
                self.conn = conn
                await self._update_sources()
                while True:
                    timeout = await self._check_dbclean()
                    await asyncio.sleep(timeout.total_seconds())

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error('DBProvider loop unhandled exception', exc_info=True)
            sys.exit(-1)

    async def _update_sources(self):
        try:
            utcnow_dt = datetime.utcnow()
            ft_now = dt_to_filetime(utcnow_dt)
            for source in self.sources:
                if source['enable']:
                    source['time'] = ft_now
                    params = {
                        key: source[key]
                        for key in
                        ['type', 'url', 'request_interval', 'table_name']
                    }
                    sql = f"INSERT INTO sources ({','.join(params.keys())}) "\
                        f"VALUES ({','.join(('@'+key for key in params.keys()))})"
                    source['id'] = await self.execute(sql, params)
                    await source['create_table'](source['table_name'])
        finally:
            self.initialized_sources.set()

    async def execute(self, sql: str, params: Optional[Dict[str, Any]]) -> int:
        async with self.lock:
            try:
                cursor = await self.conn.execute(sql, params)
                await self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                raise DBException from e

    async def executemany(self, sql: str, params: List) -> int:
        async with self.lock:
            try:
                cursor = await self.conn.executemany(sql, params)
                await self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                raise DBException from e

    async def write_data(self, table_name: str, params: Dict[str, Any]) -> int:
        sql = f"INSERT INTO {table_name} ({','.join(params.keys())}) VALUES "\
            f"({','.join(('@'+key for key in params.keys()))})"
        return await self.execute(sql, params)

    async def write_request(self, source_id: int, request_time: int,
                            status: int, **kwargs: Optional[str]) -> int:
        params = {
            'source_id': source_id,
            'request_time': request_time,
            'status': status
        }
        if 'error' in kwargs:
            params.update(error=kwargs['error'])
        return await self.write_data('requests', params)

    async def _get_last_dbclean_time(self):
        async with self.conn.execute(
                """SELECT db_time FROM db_cleans ORDER BY db_time DESC LIMIT 1;"""
        ) as cursor:
            value = await cursor.fetchone()
        return value[0] if value else None

    async def _check_dbclean(self):
        last_clean_time = await self._get_last_dbclean_time()
        config_delta = timedelta(
            seconds=timeparse(self.config['cleaning_interval']))
        utcnow_dt = datetime.utcnow()
        if not last_clean_time:
            actual_delta = config_delta + timedelta(seconds=1)
        else:
            actual_delta = utcnow_dt - filetime_to_dt(last_clean_time)

        if actual_delta > config_delta:
            await self._clean_database(utcnow_dt)
            return config_delta + timedelta(seconds=1)
        else:
            return config_delta - actual_delta + timedelta(seconds=1)

    async def _clean_database(self, utcnow_dt: datetime):
        logger.info('Clean database')
        rest_time = utcnow_dt - \
            timedelta(seconds=timeparse(self.config['request_history_age']))
        ft = dt_to_filetime(rest_time)
        async with self.lock:
            await self.conn.execute(
                "DELETE FROM requests WHERE request_time < ?", (ft, ))
            cursor = await self.conn.execute(
                "SELECT count(*) FROM sources WHERE config_time >= ?", (ft, ))
            value = await cursor.fetchone()
            if value[0] > 0:
                await self.conn.execute(
                    "DELETE FROM sources WHERE config_time < ?", (ft, ))
            await self.conn.execute(
                "INSERT INTO db_cleans (storage_period, removed_records) VALUES (?,changes())",
                (self.config['request_history_age'], ))
            await self.conn.execute(
                """DELETE FROM db_cleans WHERE rowid not in
            (SELECT rowid from db_cleans ORDER BY db_time DESC limit ?) """,
                (self.config['last_cleaning_records'], ))
            await self.conn.commit()

    async def _close(self):
        assert (self.current_task is not None)
        self.current_task.cancel()
        await self.current_task
