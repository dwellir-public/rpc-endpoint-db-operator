#!/usr/bin/env python3

from pathlib import Path
import subprocess as sp
import shutil
import constants as c


def install_apt_dependencies() -> None:
    sp.run(['apt-get', 'update'], check=True)
    sp.run(['apt', 'install', 'python3-pip', '-y'], check=True)


def install_python_dependencies(requirements_file: Path) -> None:
    # Specifically point at the system's Python, to install modules on the system level
    sp.run(['sudo', 'pip3', 'install', '-r', requirements_file], check=True)


def install_service_file(source_path: str, service_name: str) -> None:
    target_path = Path(f'/etc/systemd/system/{service_name.lower()}.service')
    shutil.copyfile(source_path, target_path)
    sp.run(['systemctl', 'daemon-reload'], check=False)


def create_env_file_for_service(service_name: str) -> None:
    with open(f'/etc/default/{service_name.lower()}', 'w', encoding='utf-8') as f:
        f.write(f"{service_name.upper()}_CLI_ARGS=''")


def generate_auth_files() -> None:
    sp.run(f'openssl rand -hex 32 > {c.JWT_SECRET_KEY_PATH}', shell=True, check=True)
    sp.run(f'openssl rand -hex 32 > {c.AUTH_PASSWORD_PATH}', shell=True, check=True)


def update_service_args(wsgi_server_port: str, service_name: str, hardcoded_args: str, restart: bool) -> None:
    args = f"{service_name.upper()}_CLI_ARGS='{hardcoded_args} --bind=0.0.0.0:{wsgi_server_port}'"
    with open(f'/etc/default/{service_name.lower()}', 'w', encoding='utf-8') as f:
        f.write(args)
    if restart:
        restart_service(service_name)


def start_service(service_name: str) -> None:
    sp.run(['systemctl', 'start', f'{service_name.lower()}.service'], check=False)


def stop_service(service_name: str) -> None:
    sp.run(['systemctl', 'stop', f'{service_name.lower()}.service'], check=False)


def restart_service(service_name: str) -> None:
    sp.run(['systemctl', 'restart', f'{service_name.lower()}.service'], check=False)


def service_running(service_name: str) -> bool:
    service_status = sp.run(['service', f'{service_name.lower()}', 'status'], stdout=sp.PIPE, check=False).returncode
    return service_status == 0
