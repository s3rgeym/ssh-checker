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
import math
import sys
from functools import partial
from multiprocessing import JoinableQueue, Process, Queue, cpu_count
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


def print_colored(text: str, color: str = 'blue', *, newline=True) -> None:
    # форматирование используем только при выводе в терминал
    if sys.stderr.isatty():
        # перемещаем курсор в начало строки и очищаем строку
        sys.stderr.write('\r\033[0K')
        text = colorize(color, text)
    sys.stderr.write(text)
    if newline:
        sys.stderr.write('\n')
    sys.stderr.flush()


print_success = partial(print_colored, color='green')
print_error = partial(print_colored, color='red')


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


def worker(in_queue, result_queue, timeout):
    while not in_queue.empty():
        try:
            username, password, hostname = in_queue.get()
            # 5 - неверные логин и/или пароль
            # 255 - порт закрыт
            retcode = check_ssh(username, password, hostname, timeout)
            if retcode == 0:
                result_queue.put_nowait(
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
            result_queue.put_nowait({'type': 'error', 'message': str(e)})
        finally:
            in_queue.task_done()
            result_queue.put_nowait({'type': 'task_done'})


def process_results(result_queue, output, total_tasks):
    writer = csv.writer(output)
    tasks_done = 0
    while True:
        result = result_queue.get()
        if result is None:
            break
        if result['type'] == 'success':
            print_success(
                '[+] '
                + ', '.join(f'{k}={v!r}' for k, v in result['details'].items())
            )
            writer.writerow(result['details'].values())
            output.flush()
        elif result['type'] == 'error':
            print_error('[!] ' + result['message'])
        elif result['type'] == 'task_done':
            tasks_done += 1
            progress = math.floor(tasks_done / total_tasks * PROGRESS_BAR_WIDTH)
            print_colored(
                'Progress: '
                + '█' * progress
                + '░' * (PROGRESS_BAR_WIDTH - progress),
                newline=False,
            )
        else:
            raise ValueError(result['type'])
    output.close()


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
        '-o',
        '--output',
        default='valid.csv',
        help='valid ssh credentials',
        type=argparse.FileType('w'),
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

    in_queue = JoinableQueue()
    for row in csv.reader(args.input):
        in_queue.put_nowait(row)

    result_queue = Queue()
    total_tasks = in_queue.qsize()

    workers = []
    for _ in range(min(args.parallel, total_tasks)):
        p = Process(
            target=worker,
            args=(in_queue, result_queue, args.timeout),
        )
        p.start()
        workers.append(p)

    result_processor = Process(
        target=process_results, args=(result_queue, args.output, total_tasks)
    )
    result_processor.start()

    in_queue.join()

    for w in workers:
        w.join()

    result_queue.put_nowait(None)
    result_processor.join()


if __name__ == '__main__':
    main()
