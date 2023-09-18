#!/usr/bin/env python3

from pathlib import Path
import subprocess as sp
import shutil
import requests
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


def set_auth_password(auth_password: str) -> None:
    with open(c.AUTH_PASSWORD_PATH, encoding='utf-8') as f:
        f.write(auth_password)


def set_jwt_secret_key(key: str) -> None:
    if is_valid_hex(key):
        with open(c.JWT_SECRET_KEY_PATH, encoding='utf-8') as f:
            f.write(key)


def is_valid_hex(string: str) -> bool:
    try:
        int(string, 16)
        return True
    except ValueError:
        return False


# TODO: merge usage with get_auth_header in db_util.py?
def get_access_token(url: str, password: str = "") -> str:
    if not password:
        with open(c.AUTH_PASSWORD_PATH, 'r', encoding='utf-8') as f:
            auth_pw = f.readline().strip()
    elif password:
        auth_pw = password
    else:
        raise ValueError("Missing authentication password for access token request!")
    token_response = requests.post(url + '/token', json={'username': c.DATABASE_USERNAME, 'password': f'{auth_pw}'}, timeout=5)
    if token_response.status_code != 200:
        raise requests.exceptions.HTTPError(f"Couldn't get access token, {token_response.text}")
    return token_response.json()["access_token"]


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
