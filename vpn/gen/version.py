import config
from os import path, makedirs, chmod
import stat
from node import VPNNode
from pyzipper import AESZipFile
from io import BytesIO


def zipfile_diff(a: bytes, b: bytes, password: str) -> bool:
    with AESZipFile(BytesIO(a), "r") as lhs, AESZipFile(BytesIO(b), "r") as rhs:
        lhs.setpassword(password.encode())
        rhs.setpassword(password.encode())

        namelist = lhs.namelist()
        if namelist != rhs.namelist():
            return True
        for filename in namelist:
            if lhs.read(filename) != rhs.read(filename):
                return True
    return False


class Version:
    def __init__(self, name: str):
        self.name = name

    @property
    def _datap(self) -> str:
        """Data path"""
        return str(path.join(config.DATA_PATH, self.name))

    @property
    def _rawp(self) -> str:
        """Raw path"""
        return str(path.join(self._datap, "raw"))

    @property
    def _zipp(self) -> str:
        """Zip path"""
        return str(path.join(self._datap, "configs"))

    def zip_path(self, name: str) -> str:
        p = str(path.join(self._zipp, f"{name}.zip"))
        return p

    def raw_path(self, name: str) -> str:
        p = str(path.join(self._rawp, name))
        return p


class OldVersion(Version):
    def __init__(self, name: str):
        super().__init__(name)

    def read_node(self, name: str, password: str,
                  subnet_ip: str, public_ip: str = None) -> VPNNode:
        p = self.zip_path(name)
        if path.exists(p):
            return VPNNode.from_cached(p, name, password, subnet_ip, public_ip)
        else:
            return VPNNode.from_meta(name, password, subnet_ip, public_ip)


class NewVersion(Version):
    def __init__(self, old: OldVersion, name: str):
        super().__init__(name)
        self.old = old
        assert not path.exists(self._datap)
        makedirs(self._datap)
        makedirs(self._rawp), makedirs(self._zipp)

    def write_node(self, node: VPNNode):
        old_zip = self.old.zip_path(node.name)
        new_content = node.export_zip()

        if path.exists(old_zip):
            with open(old_zip, "rb") as f:
                old_content = f.read()
            if zipfile_diff(old_content, new_content, node.password):
                print(f"Modified: {node.name}")
        else:
            print(f"Created: {node.name}")

        new_zip = self.zip_path(node.name)
        with open(new_zip, "wb") as f:
            f.write(new_content)

        # Perform final check
        raw_path = self.raw_path(node.name)
        with AESZipFile(new_zip, "r") as f:
            f.setpassword(node.password.encode())
            makedirs(path.join(raw_path, "hosts"))
            for filename in f.namelist():
                p = path.join(raw_path, filename)
                with open(p, "wb") as tf:
                    tf.write(f.read(filename))
                chmod(p, stat.S_IEXEC)

    def csv_path(self, name: str) -> str:
        return str(path.join(self._datap, f"{name}.csv"))
