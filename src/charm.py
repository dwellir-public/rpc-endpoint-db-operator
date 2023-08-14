#!/usr/bin/env python3
# Copyright 2023 Jakob Ersson
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk


import logging
import shutil

import ops
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus, WaitingStatus
import util
import constants as c


logger = logging.getLogger(__name__)


class EndpointDBCharm(ops.CharmBase):
    """Charms the blockchain monitoring service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """Handle changed configuration."""
        self.unit.status = MaintenanceStatus('Updating config')
        util.update_service_args(self.config.get('wsgi-server-port'), c.SERVICE_NAME, c.GUNICORN_HARDCODED_ARGS, True)
        self.unit.status = ActiveStatus('Configuration updated')

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Handle charm installation."""
        self.unit.status = MaintenanceStatus('Installing apt dependencies')
        util.install_apt_dependencies()
        self.unit.status = MaintenanceStatus('Installing Python dependencies')
        util.install_python_dependencies(self.charm_dir / 'templates/requirements_app.txt')
        self.unit.status = MaintenanceStatus('Installing script and service')
        self.install_files()
        # TODO: generate secret key and auth password automatically, to be replaced if needed?
        util.update_service_args(self.config.get('wsgi-server-port'), c.SERVICE_NAME, c.GUNICORN_HARDCODED_ARGS, False)
        self.unit.status = ActiveStatus('Installation complete')

    def install_files(self):
        self.copy_template_files()
        util.install_service_file(f'templates/etc/systemd/system/{c.SERVICE_NAME}.service', c.SERVICE_NAME)
        util.create_env_file_for_service(c.SERVICE_NAME)

    def copy_template_files(self):
        shutil.copy(self.charm_dir / 'templates/app.py', c.APP_SCRIPT_PATH)
        shutil.copy(self.charm_dir / 'templates/db_util.py', c.DB_UTIL_SCRIPT_PATH)

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

# TODO: add action to set up API access info; token/auth etc.
# TODO: add action to get API access info; token/auth etc.


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(EndpointDBCharm)
