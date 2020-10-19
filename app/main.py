# Copyright (c) 2020, Alexey Sokolov  <idales2020@outlook.com>
# Creative Commons BY-NC-SA 4.0 International Public License
# (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import argparse
from argparse import Namespace
import asyncio
import json
import logging
import os
import signal
import sys
from typing import Dict, Any

from app.runner import Runner


def get_script_path() -> str:
    return os.path.dirname(os.path.realpath(sys.argv[0]))


def parse_args() -> Namespace:
    """parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        help='Path to the configuration file',
                        default='')
    return parser.parse_args()


def load_configuration(args: Namespace) -> Dict:
    """load configuration"""
    with open(args.config) as file:
        return json.load(file)['configuration']


def main() -> None:
    # parse command line arguments
    args = parse_args()
    if not args.config:
        args.config = os.path.join(get_script_path(), 'config', 'config.json')

    config = load_configuration(args)
    logconfig = config.get('logger', None)
    logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    numeric_level = logging.INFO
    filename = None
    if logconfig:
        loglevel = logconfig.get('level', 'INFO')
        filename = logconfig.get('filename', None)
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)

    logging.basicConfig(format=logformat,
                        level=numeric_level,
                        filename=filename)
    logger = logging.getLogger(__name__)

    loop = asyncio.get_event_loop()

    def graceful_shutdown(signum: Any = None, frame: Any = None) -> None:
        logger.info('SERVICE SHUTTING DOWN...')
        loop.stop()

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame), graceful_shutdown,
                                signame)

    logger.info('SERVICE STARTED')
    try:
        with Runner(config):
            loop.run_forever()
    except KeyboardInterrupt:
        graceful_shutdown()
    finally:
        # Let's also finish all running tasks:
        pending = asyncio.Task.all_tasks()
        # Run loop until tasks done:
        loop.run_until_complete(asyncio.gather(*pending))
        loop.close()
    logger.info('SERVICE FINISHED')


if __name__ == '__main__':
    main()
