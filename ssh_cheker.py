#!/usr/bin/env python3
"""
 ____ ____  _   _    ____ _     _____      _
/ ___/ ___|| | | |  / ___| |__ |___ /  ___| | _____ _ __
\___ \___ \| |_| | | |   | '_ \  |_ \ / __| |/ / _ \ '__|
 ___) |__) |  _  | | |___| | | |___) | (__|   <  __/ |
|____/____/|_| |_|  \____|_| |_|____/ \___|_|\_\___|_|
"""
import argparse
import csv
import json
import math
import sys
from enum import Enum
from multiprocessing import JoinableQueue, Process, cpu_count
from subprocess import DEVNULL, Popen
from urllib.parse import _splitport

__version__ = '0.1.0'

LF = '\n'


class ProgressBar:
    def __init__(self, q, bars=20):
        self._q = q
        self._total = q.qsize()
        self._bars = bars

    def render(self):
        n = math.ceil(
            (self._total - self._q.qsize()) / self._total * self._bars
        )
        return '█' * n + '░' * (self._bars - n)

    __str__ = render


# =============================================================================
# Форматирование
# =============================================================================
class Formatting(Enum):
    CLEAR = '\r\033[0K'
    END = '\033[0m'


class Color(Enum):
    BLACK = '\033[0;30m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[0;37m'
    PRIMARY = BLUE
    SUCCESS = GREEN
    ERROR = RED


def colored(s, color):
    color = Color[color.upper()] if isinstance(color, str) else color
    return f'{color.value}{s}{Formatting.END.value}'


def output(
    message,
    color='primary',
    *,
    append_lf=True,
    clear=True,
    flush=True,
    prepend_lf=False,
    stderr=False,
):
    stream = sys.stderr if stderr else sys.stdout
    if prepend_lf:
        stream.write(LF)
    # форматирование используем только при выводе в терминал
    if stream.isatty():
        if clear:
            stream.write(Formatting.CLEAR.value)
        message = colored(message, color)
    stream.write(message)
    if append_lf:
        stream.write(LF)
    if flush:
        stream.flush()


# =============================================================================


def check_ssh(username, password, hostname, timeout=10):
    host, port = _splitport(hostname)
    cmd = [
        'sshpass',
        '-p',
        password,
        'ssh',
        '-p',
        port or '22',
        '-T',
        '-o',
        f'ConnectTimeout={timeout}',
        '-o',
        'PreferredAuthentications=password',
        '-o',
        'UserKnownHostsFile=/dev/null',
        '-o',
        'StrictHostKeyChecking=no',
        f'{username}@{host}',
    ]
    # stdin=DEVNULL чтобы предотвратить ожидание ввода
    p = Popen(cmd, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
    p.communicate()
    return p.returncode


def worker(q, pb, timeout):
    while not q.empty():
        try:
            username, password, hostname = row = q.get()
            # 5 - неверные логин и/или пароль
            # 255 - порт закрыт
            rc = check_ssh(username, password, hostname, timeout)
            if 0 == rc:
                output(
                    json.dumps(
                        dict(zip(('username', 'password', 'hostname'), row)),
                        ensure_ascii=False,
                    ),
                    'success',
                )
        except Exception as e:
            output(f"[!] {e}", 'error', stderr=True)
        finally:
            q.task_done()
            output(str(pb), append_lf=False, stderr=True)


class ArgumentFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=ArgumentFormatter,
    )
    parser.add_argument(
        '-i',
        '--input',
        default='data.csv',
        help='ssh credentials. fields: user, password, hostname[:port]',
        type=argparse.FileType('r'),
    )
    parser.add_argument(
        '-t',
        '--timeout',
        help='connect timeout',
        default=10,
        type=int,
    )
    parser.add_argument(
        '-p',
        '--parallel',
        help='number of parallel processes',
        default=cpu_count(),
        type=int,
    )
    parser.add_argument(
        '-v', '--version', action='version', version=f'%(prog)s {__version__}'
    )
    args = parser.parse_args()

    q = JoinableQueue()
    for row in csv.reader(args.input):
        q.put_nowait(row)
    pb = ProgressBar(q)
    workers = []
    for _ in range(min(args.parallel, q.qsize())):
        p = Process(target=worker, args=(q, pb, args.timeout))
        p.start()
        workers.append(p)

    q.join()
    for w in workers:
        w.join()


if __name__ == '__main__':
    main()
