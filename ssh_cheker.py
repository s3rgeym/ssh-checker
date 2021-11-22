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
import sys
import warnings
from functools import partial
from multiprocessing import JoinableQueue, Process, Queue, cpu_count
from subprocess import DEVNULL, Popen
from urllib.parse import splitport

# splitport deprecated warning
warnings.filterwarnings('ignore')

__version__ = '0.1.0'

PROGRESS_WIDTH = 20


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


def colorize(text, color):
    return f'\033[0;{color_map[color]}m{text}\033[0m'


def console_write(text: str, color: str = 'blue', *, newline=True):
    # форматирование используем только при выводе в терминал
    # if sys.stderr.isatty():
    #     ...
    # перемещаем курсор в начало строки и очищаем строку
    sys.stderr.write('\r\033[0K')
    colored = colorize(text, color)
    sys.stderr.write(colored)
    if newline:
        sys.stderr.write('\n')
    sys.stderr.flush()


console_success = partial(console_write, color='green')
console_error = partial(console_write, color='red')


def console_progress(value, total):
    ratio = value / total
    percentage = round(ratio * 100)
    value_width = round(ratio * PROGRESS_WIDTH)
    progress_indicator = '█' * value_width + '░' * (
        PROGRESS_WIDTH - value_width
    )
    console_write(f'{progress_indicator} {percentage}%', newline=False)


def check_ssh(username, password, hostname, timeout=10):
    host, port = splitport(hostname)
    cmd_args = [
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
    p = Popen(cmd_args, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
    p.communicate()
    return p.returncode


def worker(in_q, result_q, timeout):
    while not in_q.empty():
        try:
            username, password, hostname = in_q.get()
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
            in_q.task_done()
            result_q.put_nowait({'type': 'task_done'})


def output_results(result_q, output, total_tasks):
    writer = csv.writer(output)
    tasks_done = 0
    while True:
        result = result_q.get()
        if result is None:
            break
        if result['type'] == 'success':
            details = result['details']
            console_success(
                f"[VALID] {details['username']}@{details['hostname']}"
            )
            writer.writerow(details.values())
            output.flush()
        elif result['type'] == 'error':
            console_error(f"[ERROR] {result['message']}")
        elif result['type'] == 'task_done':
            tasks_done += 1
            console_progress(tasks_done, total_tasks)
        else:
            raise ValueError(result['type'])


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '-i',
        '--input',
        default=sys.stdin,
        help='SSH credentials in CSV format. Fields: user, password, hostname[:port]. Default: <STDIN>',
        type=argparse.FileType('r'),
    )
    parser.add_argument(
        '-o',
        '--output',
        default=sys.stdout,
        help='Valid SSH credentials in CSV format. Default: <STDOUT>',
        type=argparse.FileType('w'),
    )
    parser.add_argument(
        '-t',
        '--timeout',
        help='Connect timeout. Default: %(default)s',
        default=10,
        type=int,
    )
    parser.add_argument(
        '-p',
        '--parallel',
        help='Number of parallel workers. Default: number_of_processors * 2',
        default=cpu_count() * 2,
        type=int,
    )
    parser.add_argument(
        '-v', '--version', action='version', version=f'%(prog)s {__version__}'
    )
    args = parser.parse_args()

    in_q = JoinableQueue()
    for row in csv.reader(args.input):
        in_q.put_nowait(row)

    total_tasks = in_q.qsize()
    result_q = Queue()

    workers = []
    for _ in range(min(args.parallel, total_tasks)):
        p = Process(
            target=worker,
            args=(in_q, result_q, args.timeout),
        )
        p.start()
        workers.append(p)

    output_p = Process(
        target=output_results, args=(result_q, args.output, total_tasks)
    )
    output_p.start()

    in_q.join()

    for w in workers:
        w.join()

    result_q.put_nowait(None)
    output_p.join()


if __name__ == '__main__':
    main()
