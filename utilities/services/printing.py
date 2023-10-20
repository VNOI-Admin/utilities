import subprocess

from config import ServiceCoord

from .base import Service
from .rpc import rpc_method


class PrintingService(Service):
    def __init__(self):
        super().__init__()
        self.user_service = self.connect_to(ServiceCoord('UserService', 0))

    @rpc_method
    def print(self, source):
        print(f'[PRINT] Printing {source}')
        subprocess.Popen(f'lpr -o media=A4 -o prettyprint -o page-border=single -o fit-to-page {source}')
