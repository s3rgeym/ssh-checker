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
from multiprocessing import JoinableQueue, Process, Queue, Value, cpu_count
from subprocess import DEVNULL, Popen
from urllib.parse import _splitport

__version__ = '0.1.0'

PROGRESS_BAR_WIDTH = 20


color_map = {
    'black': 30,
    'red': 31,
    'green': 32,
    'yellow': 33,
    'blue': 34,
    'purple': 35,
    'cyan': 36,
    'white': 37,
}


def colorize(color: str, text: str) -> str:
    return f'\033[0;{color_map[color]}m{text}\033[0m'


def output(
    text: str, color: str = 'blue', *, stream=sys.stdout, newline=True
) -> None:
    # форматирование используем только при выводе в терминал
    if stream.isatty():
        # перемещаем курсор в начало строки и очищаем строку
        stream.write('\r\033[0K')
        text = colorize(color, text)
    stream.write(text)
    if newline:
        stream.write('\n')
    stream.flush()


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


def worker(q, result_q, tasks_done, timeout):
    while not q.empty():
        try:
            username, password, hostname = q.get()
            # 5 - неверные логин и/или пароль
            # 255 - порт закрыт
            retcode = check_ssh(username, password, hostname, timeout)
            if retcode == 0:
                result_q.put_nowait(
                    {
                        'type': 'success',
                        'details': dict(
                            username=username,
                            password=password,
                            hostname=hostname,
                        ),
                    }
                )
        except Exception as e:
            result_q.put_nowait({'type': 'error', 'message': str(e)})
        finally:
            q.task_done()
            tasks_done.value += 1
            result_q.put_nowait({'type': 'task_done'})


def output_results(q, total_tasks, tasks_done):
    while True:
        result = q.get()
        if result is None:
            break
        if result['type'] == 'success':
            output(json.dumps(result['details'], ensure_ascii=False), 'green')
        elif result['type'] == 'error':
            output(result['message'], 'red', stream=sys.stderr)
        elif result['type'] == 'task_done':
            progress = math.floor(
                tasks_done.value / total_tasks * PROGRESS_BAR_WIDTH
            )
            output(
                'Progress: '
                + '█' * progress
                + '░' * (PROGRESS_BAR_WIDTH - progress),
                stream=sys.stderr,
                newline=False,
            )
        else:
            raise ValueError(result['type'])


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

    result_q = Queue()
    total_tasks = q.qsize()
    tasks_done = Value('i', 0)

    workers = []
    for _ in range(min(args.parallel, total_tasks)):
        p = Process(target=worker, args=(q, result_q, tasks_done, args.timeout))
        p.start()
        workers.append(p)

    output_p = Process(
        target=output_results, args=(result_q, total_tasks, tasks_done)
    )
    output_p.start()

    q.join()

    for w in workers:
        w.join()

    result_q.put_nowait(None)
    output_p.join()


if __name__ == '__main__':
    main()
