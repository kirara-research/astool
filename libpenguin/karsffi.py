import ctypes
import os
from typing import Optional

class PenguinKeyset(ctypes.Structure):
    _fields_ = [
        ("k1", ctypes.c_uint32),
        ("k2", ctypes.c_uint32),
        ("k3", ctypes.c_uint32),
    ]

LIBRARY = None

def default_libpath():
    return os.path.join(os.path.dirname(__file__), "libpenguin.dylib")

def init(libpath: Optional[str] = None):
    global LIBRARY
    LIBRARY = ctypes.cdll.LoadLibrary(libpath or default_libpath())
    LIBRARY.penguin_decrypt_buf.argtypes = [ctypes.POINTER(PenguinKeyset),
        ctypes.c_char_p, ctypes.c_int]

def decrypt(keyset: PenguinKeyset, buf: bytearray):
    if not LIBRARY:
        raise RuntimeError("Penguin library has not been initialized")
    LIBRARY.penguin_decrypt_buf(keyset, buf, len(buf))
