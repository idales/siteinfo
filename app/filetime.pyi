from datetime import datetime, timedelta, tzinfo
from typing import Optional

EPOCH_AS_FILETIME: int  # January 1, 1970 as MS file time
HUNDREDS_OF_NANOSECONDS: int


class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt: Optional[datetime]) -> Optional[timedelta]:
        ...

    def tzname(self, dt: Optional[datetime]) -> Optional[str]:
        ...

    def dst(self, dt: Optional[datetime]) -> Optional[timedelta]:
        ...


def dt_to_filetime(dt: datetime) -> int:
    ...


def filetime_to_dt(ft: int) -> datetime:
    ...
