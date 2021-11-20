# SSH Checker

SSH Account Checker. 

![image](https://user-images.githubusercontent.com/12753171/142739623-14fbf098-d6e9-4395-81e3-286f57d73749.png)

```zsh
ssh-checker on  main [!] via 🐍 v3.10.0
➜ ./ssh_cheker.py -h
usage: ssh_cheker.py [-h] [-i INPUT] [-t TIMEOUT] [-p PARALLEL] [-v]

 ____ ____  _   _    ____ _     _____      _
/ ___/ ___|| | | |  / ___| |__ |___ /  ___| | _____ _ __
\___ \___ \| |_| | | |   | '_ \  |_ \ / __| |/ / _ \ '__|
 ___) |__) |  _  | | |___| | | |___) | (__|   <  __/ |
|____/____/|_| |_|  \____|_| |_|____/ \___|_|\_\___|_|

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        ssh credentials. fields: user, password, hostname[:port] (default: data.csv)
  -t TIMEOUT, --timeout TIMEOUT
                        connect timeout (default: 10)
  -p PARALLEL, --parallel PARALLEL
                        number of parallel processes (default: 24)
  -v, --version         show program's version number and exit
```

## Features

- no python dependencies
- multiprocessing

## System Requirements

- Python >= 3.7.3
- [sshpass](https://sourceforge.net/projects/sshpass/)
