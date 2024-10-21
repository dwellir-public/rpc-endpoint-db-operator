#!/usr/bin/env python3
# Copyright 2023 Jakob Ersson
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk


import logging
import shutil
import subprocess as sp
import time

import ops
from ops.charm import ActionEvent, CharmBase
from ops.model import ActiveStatus, MaintenanceStatus, ModelError, WaitingStatus

import constants as c
import util

logger = logging.getLogger(__name__)


class EndpointDBCharm(CharmBase):
    """Charms the blockchain monitoring service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

        # API actions
        self.framework.observe(self.on.get_access_token_action, self._on_get_access_token_action)
        # TODO: before committing to below, figure out how to make use of db_util in both charm and in-containter without introducing code duplication
        # TODO: add chain
        # TODO: add RPC
        # TODO: list chains
        # TODO: list RPCs
        # TODO: show chain info
        # TODO: delete RPC
        # TODO: delete chain
        # TODO: import from JSON (with/without overwrite protection?)
        # File actions
        self.framework.observe(self.on.get_auth_password_action, self._on_get_auth_password_action)
        self.framework.observe(self.on.set_auth_password_action, self._on_set_auth_password_action)
        self.framework.observe(self.on.get_jwt_secret_key_action, self._on_get_jwt_secret_key_action)
        self.framework.observe(self.on.set_jwt_secret_key_action, self._on_set_jwt_secret_key_action)

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Handle charm installation."""
        self.unit.status = MaintenanceStatus('Installing apt dependencies')
        util.install_apt_dependencies()
        self.unit.status = MaintenanceStatus('Installing Python dependencies')
        util.install_python_dependencies(self.charm_dir / 'templates/requirements_app.txt')
        self.unit.status = MaintenanceStatus('Installing script and service')
        self.install_files()
        util.generate_auth_files()
        util.update_service_args(self.config.get('wsgi-server-port'), c.SERVICE_NAME, c.GUNICORN_HARDCODED_ARGS, False)
        self.import_db_from_resources()
        self.unit.status = ActiveStatus('Installation complete')

    def install_files(self) -> None:
        self.copy_template_files()
        util.install_service_file(f'templates/etc/systemd/system/{c.SERVICE_NAME}.service', c.SERVICE_NAME)
        util.create_env_file_for_service(c.SERVICE_NAME)

    def copy_template_files(self) -> None:
        shutil.copy(self.charm_dir / 'templates/app.py', c.APP_SCRIPT_PATH)
        shutil.copy(self.charm_dir / 'templates/db_util.py', c.DB_UTIL_SCRIPT_PATH)

    def import_db_from_resources(self) -> None:
        try:
            rpc_chains_path = self.model.resources.fetch('rpc-chains')
            rpc_urls_path = self.model.resources.fetch('rpc-urls')
            rpc_chains = util.load_json_file(rpc_chains_path)
            rpc_urls = util.load_json_file(rpc_urls_path)
            util.start_service(c.SERVICE_NAME)  # Start service to initialize DB before import
            time.sleep(5)  # Give service time to initialize DB
            util.local_import_from_json_files(rpc_chains, rpc_urls, str(c.DATABASE_PATH))
        except (NameError, ModelError) as e:
            logger.error('Error trying to import DB from resources: %s', e)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """Handle changed configuration."""
        self.unit.status = MaintenanceStatus('Updating config')
        util.update_service_args(self.config.get('wsgi-server-port'), c.SERVICE_NAME, c.GUNICORN_HARDCODED_ARGS, True)
        self.unit.status = ActiveStatus('Configuration updated')

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        util.start_service(c.SERVICE_NAME)

    def _on_stop(self, event: ops.StopEvent):
        """Handle stop event."""
        util.stop_service(c.SERVICE_NAME)

    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle status update."""
        if not util.service_running(c.SERVICE_NAME):
            self.unit.status = WaitingStatus("Service not yet started")
            return
        self.unit.status = ActiveStatus("Service running")

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent):
        """Handle charm upgrade."""
        util.stop_service(c.SERVICE_NAME)
        self.install_files()
        util.update_service_args(self.config.get('wsgi-server-port'), c.SERVICE_NAME, c.GUNICORN_HARDCODED_ARGS, False)
        util.start_service(c.SERVICE_NAME)

    def _on_get_access_token_action(self, event: ActionEvent) -> None:
        event.log("Getting API access token...")
        try:
            event.set_results(results={'access-token': util.get_access_token(f'http://localhost:{self.config.get("wsgi-server-port")}')})
        except sp.CalledProcessError as e:
            logger.error('Error trying to get the API access token: %s', e)
            event.fail("Unable to get API access token")

    def _on_get_auth_password_action(self, event: ActionEvent) -> None:
        event.log("Getting API auth password...")
        try:
            key = sp.check_output(['cat', c.AUTH_PASSWORD_PATH]).decode('utf-8').strip()
            event.set_results(results={'auth-password': key})
        except sp.CalledProcessError as e:
            logger.error('Error trying to get the API auth password: %s', e)
            event.fail("Unable to get API auth password")

    def _on_get_jwt_secret_key_action(self, event: ActionEvent) -> None:
        event.log("Getting JWT secret key...")
        try:
            key = sp.check_output(['cat', c.JWT_SECRET_KEY_PATH]).decode('utf-8').strip()
            event.set_results(results={'jwt-secret-key': key})
        except sp.CalledProcessError as e:
            logger.error('Error trying to get JWT secret key: %s', e)
            event.fail("Unable to get JWT secret key")

    def _on_set_auth_password_action(self, event: ActionEvent) -> None:
        event.log("Setting auth password...")
        try:
            pw = event.params['password']
            util.set_auth_password(pw)
        except ValueError as e:
            event.fail("Unable to set auth password: %s", e)

    def _on_set_jwt_secret_key_action(self, event: ActionEvent) -> None:
        event.log("Setting JWT secret key...")
        try:
            key = event.params['key']
            util.set_jwt_secret_key(key)
        except ValueError as e:
            event.fail("Unable to set JWT secret key: %s", e)


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(EndpointDBCharm)
