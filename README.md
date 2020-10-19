# Siteinfo service

## Description

The service is designed to receive site data and
saving them to a database for further analyzes.
Current version supports SQLite as database provider.
To parse the information received from various sites,
a system of plugins has been implemented.
The current version has a plugin that processes
a two-week weather forecast from the gismeteo website.
Service works on ubuntu operating systems. Tested with
Ubuntu 18.04.

## Config file format

- Config header with current file version.

```json
{
    "version": "0.0.1",
    "configuration":
    {
```

- Logging level by default.
  Also **filename** could be set to output log to the file.

```json
        "logger":
        {
            "level":"INFO"
        },
```

- Database options:
  - **cleaning interval** – interval between cleanup procedure calls
  - **request_history age** – storage time of request history
  - **last_cleaning_records** – information about each cleaning stored in database.
    parameter determines the number of such records that remain in the database

```json
        "database":
        {
            "cleaning_interval": "15 min",
            "request_history_age": "50 min",
            "last_cleaning_records": 10
        }
```

- Sources section. List of monitored sources.
  - **enable** – if set to true monitoring enabled for the item
  - **type** – parsing plugin type
  - **url** – url for original data
  - **request_interval** – the interval between adjacent requests.
  The request time is determined by a grid of time units. For example,
  requests with 12 hour intervals occur at noon and midnight.
  - table_name – the name of the sql table in which the query data is stored

```json
        "sources":
        [
            {
                "enable": true,
                "type":"gismeteo-2week",
                "url":"https://www.gismeteo.ru/weather-novosibirsk-4690/2-weeks/",
                "request_interval":"12 min",
                "table_name": "gismeteo_novosib"
            }
        ]
    }
}

```

## Deb package building

Building the package is done by cmake tool.
To install cmake run ```sudo apt install cmake```.

- From source root folder create build directory and enter to it .

``` bash
mkdir build && cd build
```

- Configure by cmake

``` bash
cmake ../install
```

- Make package by

``` bash
cpack
```

The deb package will appear in the build folder.

## Deb package installation and health check

- To install deb package run ```sudo apt install ./siteinfo-1.0.0-Linux.deb```.
- The service is installed to folder ```/opt/siteinfo```.
- Service status can be checked by ```systemctl status siteinfo.service```.
- To view current service output run ```journalctl -fu siteinfo.service```.
- Database can be checked by ```sqlitebrowser``` tool.
  Installation is done with ```sudo apt install sqlitebrowser```
- To remove the package run ```sudo apt remove siteinfo```
  or ```sudo apt purge siteinfo``` to remove database file also
