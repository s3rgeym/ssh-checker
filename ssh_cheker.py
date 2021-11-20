#!/usr/bin/env python3
"""SSH Checker"""
import argparse
import csv
import math
import sys
from enum import Enum
from multiprocessing import JoinableQueue, Process, cpu_count
from subprocess import DEVNULL, Popen
from urllib.parse import _splitport


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
    clear=False,
    flush=True,
    newline=True,
    stderr=False,
):
    file = sys.stderr if stderr else sys.stdout
    # форматирование используем только при выводе в терминал
    # if sys.stdout.isatty():
    if clear:
        file.write(Formatting.CLEAR.value)
    message = colored(message, color)
    file.write(message)
    if newline:
        file.write('\n')
    if flush:
        file.flush()


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


def worker(q, timeout):
    while not q.empty():
        try:
            username, password, hostname = q.get()
            # 5 - неверные логин и/или пароль
            # 255 - порт закрыт
            code = check_ssh(username, password, hostname, timeout)
            if code == 0:
                output(
                    f"[OK]\t{username!r}\t{password!r}\t{hostname!r}",
                    'success',
                )
        except Exception as e:
            output(f"err: {e}", 'error')
        finally:
            q.task_done()
            # output(f'queue size:\t{q.qsize()}', clear=True, newline=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-i',
        '--input',
        default='data.scv',
        help='format: user,password,hostname[:port]<NL>',
        type=argparse.FileType('r'),
    )
    parser.add_argument(
        '-t',
        '--timeout',
        help='connect timeout (default: %(default)s)',
        default=10,
        type=int,
    )
    parser.add_argument(
        '-p',
        '--processes',
        help='number of parallel processes (default: %(default)s)',
        default=cpu_count() * 2,
        type=int,
    )
    args = parser.parse_args()

    q = JoinableQueue()
    for username, password, hostname in csv.reader(args.input):
        q.put_nowait((username, password, hostname))

    workers = []
    for _ in range(min(args.processes, q.qsize())):
        p = Process(target=worker, args=(q, args.timeout))
        p.start()
        workers.append(p)

    q.join()
    for w in workers:
        w.join()


if __name__ == '__main__':
    main()
