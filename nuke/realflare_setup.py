import logging
import os
import platform
import subprocess
import sys

logger = logging.getLogger('realflare')


class Setup:
    url = 'https://github.com/beatreichenbach/realflare/archive/refs/heads/main.zip'

    def __init__(self, venv_path: str = ''):
        # venv path
        if not venv_path:
            venv_path = os.path.join(os.path.dirname(__file__), 'venv')
        self.venv_path = venv_path

        if platform.system() == 'Windows':
            # lib
            self.lib_path = os.path.join(venv_path, 'Lib', 'site-packages')
            # executable
            self.executable = os.path.join(venv_path, 'Scripts', 'python.exe')
        else:
            major, minor = sys.version_info[:2]
            lib_dir = os.path.join('lib', f'python{major:d}.{minor:d}')
            # lib
            self.lib_path = os.path.join(venv_path, lib_dir, 'site-packages')
            # executable
            self.executable = os.path.join(venv_path, 'bin', 'python3')

    def venv(self) -> None:
        logger.info('Installing virtual environment ...')

        executable = os.path.join(
            os.path.dirname(sys.executable), os.path.basename(self.executable)
        )
        subprocess.run(f'{executable} -m venv {self.venv_path}', shell=True)
        subprocess.run(f'{self.executable} -m ensurepip', shell=True)
        subprocess.run(f'{self.executable} -m pip install --upgrade pip', shell=True)

    def install(self) -> None:
        logger.info('Installing pip packages ...')
        subprocess.run(
            f'{self.executable} -m pip install realflare@{self.url}', shell=True
        )

    def create_shortcut(self) -> None:
        logger.info('Creating Shortcut ...')
        if platform.system() == 'Windows':
            filename = os.path.join(self.venv_path, '..', 'Realflare.lnk')
            icon_path = os.path.join(self.lib_path, 'realflare', 'assets', 'icon.ico')
            target_path = os.path.join(os.path.dirname(self.executable), 'pythonw.exe')
            arguments = '-m realflare --gui'
            command = (
                f"$ws = New-Object -ComObject WScript.Shell; "
                f"$s = $ws.CreateShortcut('{filename}'); "
                f"$S.TargetPath = '{target_path}'; "
                f"$S.IconLocation = '{icon_path}'; "
                f"$S.Arguments = '{arguments}'; "
                f"$S.Save()"
            )
            subprocess.run(
                'powershell.exe -ExecutionPolicy Bypass -NoLogo -NonInteractive '
                f'-NoProfile -Command "{command}"',
                shell=True,
            )
        else:
            return

    def run(self):
        logger.setLevel(logging.INFO)
        try:
            self.venv()
            self.install()
            self.create_shortcut()
        except subprocess.CalledProcessError as e:
            logger.exception(e)
            logger.error('Installation failed')
        logger.setLevel(logging.WARNING)


if __name__ == '__main__':
    setup = Setup()
    setup.run()
