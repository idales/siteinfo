# Copyright (c) 2020, Alexey Sokolov  <idales2020@outlook.com>
# Creative Commons BY-NC-SA 4.0 International Public License
# (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import sqlite3

import aiosqlite3


class DBScripts:

    DATABASE_VERSION = 1

    DATABASE_SETTINGS = """
    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;
    """

    UPDATE_DATABASE_INCREMENTAL = {
        0:
        """
    CREATE TABLE sources (
        source_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        'type'	           TEXT NOT NULL,
        url                TEXT NOT NULL,
        request_interval   TEXT NOT NULL,
        table_name         TEXT NOT NULL,
        config_time        INTEGER DEFAULT (CAST((julianday('now')-julianday('1601-01-01'))*864000000000 as integer))
        );

    CREATE VIEW source_view AS
    SELECT
        source_id,
        'type',
        url,
        strftime('%Y-%m-%dT%H:%M:%f',config_time / 10000000.0-11644473600.0, 'unixepoch') as config_time,
        request_interval,
        table_name
    FROM
        sources
    ORDER BY source_id;


    CREATE TABLE requests (
        request_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id           INTEGER REFERENCES sources(source_id) ON UPDATE CASCADE ON DELETE CASCADE,
        request_time        INTEGER DEFAULT (CAST((julianday('now')-julianday('1601-01-01'))*864000000000 as integer)),
        status              INTEGER NOT NULL,
        error               TEXT
        );

    CREATE VIEW request_view AS
    SELECT
        request_id,
        type,
        url,
        strftime('%Y-%m-%dT%H:%M:%f',request_time/10000000.0-11644473600.0,'unixepoch') as request_time,
        status,
        error
    FROM
        requests
        JOIN sources USING (source_id)
    ORDER BY request_id;

    CREATE TABLE db_cleans(
        db_time             INTEGER DEFAULT (CAST((julianday('now')-julianday('1601-01-01'))*864000000000 as integer)),
        storage_period      TEXT,
        removed_records     INTEGER
        );

    CREATE VIEW db_clean_view AS
    SELECT
        strftime('%Y-%m-%dT%H:%M:%f',db_time/10000000.0-11644473600.0,'unixepoch') as db_time,
        storage_period,
        removed_records
    FROM
        db_cleans
    ORDER BY db_time;

    CREATE INDEX "config_time_index" ON "sources" (
        "config_time"
    );

    CREATE INDEX "request_time_index" ON "requests" (
        "request_time");


    """ + f'PRAGMA user_version = {DATABASE_VERSION};'
    }

    @staticmethod
    async def create_connection(filename: str) -> aiosqlite3.Connection:
        connection = await aiosqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        # verify database version
        read_version = (await (await connection.execute('PRAGMA user_version')).fetchone())[0]
        if read_version > DBScripts.DATABASE_VERSION:
            raise RuntimeError(
                f'Unexpected database version: read_version={read_version} code_version={DBScripts.DATABASE_VERSION}.')
        await connection.executescript(DBScripts.DATABASE_SETTINGS)
        for version in range(read_version, DBScripts.DATABASE_VERSION):
            if version in DBScripts.UPDATE_DATABASE_INCREMENTAL:
                await connection.executescript(DBScripts.UPDATE_DATABASE_INCREMENTAL[version])
        await connection.commit()
        return connection
