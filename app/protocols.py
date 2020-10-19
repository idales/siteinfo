from typing_extensions import AsyncContextManager
from typing import Any, Dict, Optional, List


class DBProviderProtocol(AsyncContextManager):

    async def execute(self, sql: str, params: Optional[Dict]) -> int:
        ...

    async def executemany(self, sql: str, params: List) -> int:
        ...

    async def write_request(self, source_id: int, request_time: int,
                            status: int, **kwargs: Optional[str]) -> int:
        ...

    async def write_data(self, table_name: str,
                         params: Dict[str, Any]) -> Optional[int]:
        ...

    @staticmethod
    def get_syntax() -> str:
        ...


class PluginProtocol():

    async def create_sql_table_if_not_exists(self, table_name: str) -> int:
        ...

    async def parse(self, text: str, request_id: int,
                    table_name: str) -> None:
        ...
