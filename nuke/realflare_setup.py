import logging
import os
import platform
import subprocess


logger = logging.getLogger('realflare')


class Setup:
    url = 'https://github.com/beatreichenbach/realflare/archive/refs/heads/main.zip'

    def __init__(self, venv_path: str = ''):
        if not venv_path:
            venv_path = os.path.join(os.path.dirname(__file__), 'venv')

        # venv
        self.venv_path = venv_path
        lib_dir = 'Lib' if platform.system() == 'Windows' else 'lib'
        self.lib_path = os.path.join(self.venv_path, lib_dir, 'site-packages')

        # executable
        bin_dir = 'Scripts' if platform.system() == 'Windows' else 'bin'
        self.executable = os.path.join(self.venv_path, bin_dir, 'python')

    def venv(self) -> None:
        logger.info('Installing virtual environment ...')
        subprocess.run(f'python -m venv {self.venv_path}', shell=True)

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
        try:
            self.venv()
            self.install()
            self.create_shortcut()
        except subprocess.CalledProcessError as e:
            logger.exception(e)
            logger.error('Installation failed')


if __name__ == '__main__':
    setup = Setup()
    setup.run()
