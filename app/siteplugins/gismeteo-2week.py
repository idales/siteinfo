# Copyright (c) 2020, Alexey Sokolov  <idales2020@outlook.com>
# Creative Commons BY-NC-SA 4.0 International Public License
# (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

from datetime import date
from typing import Any, Dict, List

from bs4 import BeautifulSoup, SoupStrainer

from app.protocols import DBProviderProtocol


class SQLiteSyntax:
    @staticmethod
    async def create_table_if_not_exists(db_provider: DBProviderProtocol,
                                         table_name: str) -> int:
        sql = f"""CREATE TABLE IF NOT EXISTS {table_name} (
                request_id  REFERENCES requests(request_id) ON UPDATE CASCADE ON DELETE CASCADE,
                date DATE NOT NULL,
                maxt int not null,
                mint int not null);
        """
        return await db_provider.execute(sql, None)

    @staticmethod
    async def save_data(db_provider: DBProviderProtocol, table_name: str,
                        data: List[Dict[str, Any]]) -> int:
        sql = f"INSERT INTO {table_name} (request_id, date, maxt, mint) VALUES "\
            "(@request_id, @date, @maxt, @mint);"
        return await db_provider.executemany(sql, data)


class Siteplugin:
    def __init__(self, db_provider: DBProviderProtocol):
        self.db_provider = db_provider
        self.sql_syntax = {'sqlite': SQLiteSyntax}[db_provider.get_syntax()]

    async def parse(self, text: str, request_id: int, table_name: str) -> None:
        forecast = SoupStrainer('div', attrs={"data-widget-id": "forecast"})
        soup = BeautifulSoup(text, 'lxml', parse_only=forecast)
        temperatures = soup.select('span.unit_temperature_c')
        cur_ordinal = date.today().toordinal()
        templist = []
        for maxt, mint in zip(temperatures[::2], temperatures[1::2]):
            cur_date = date.fromordinal(cur_ordinal)
            templist.append({
                'request_id': request_id,
                'date': cur_date,
                'maxt': int(maxt.string.replace('−', '-')),
                'mint': int(mint.string.replace('−', '-'))
            })
            cur_ordinal += 1
        await self.sql_syntax.save_data(self.db_provider, table_name, templist)

    async def create_sql_table_if_not_exists(self, table_name: str) -> int:
        return await self.sql_syntax.create_table_if_not_exists(
            self.db_provider, table_name)
