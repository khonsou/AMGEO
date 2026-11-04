"""Project-scoped credential storage; credentials never enter JSON state."""
from __future__ import annotations

import ctypes
import hashlib
from pathlib import Path
import sys


class MemoryVault:
    storage = "memory"

    def __init__(self, root=None): self.value = None
    def set(self, value): self.value = value
    def get(self): return self.value


class MacKeychainVault(MemoryVault):
    def __init__(self, root):
        super().__init__()
        self.service = b"com.angrymiao.amseo.question-eval"
        self.account = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:24].encode()
        self.security = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self.cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]
        self.security.SecKeychainFindGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        self.security.SecKeychainAddGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.security.SecKeychainItemModifyAttributesAndData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        self.security.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.security.SecKeychainGetUserInteractionAllowed.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        self.security.SecKeychainSetUserInteractionAllowed.argtypes = [ctypes.c_ubyte]

    def _query(self):
        length, data, item = ctypes.c_uint32(), ctypes.c_void_p(), ctypes.c_void_p()
        status = self.security.SecKeychainFindGenericPassword(None, len(self.service), self.service, len(self.account), self.account, ctypes.byref(length), ctypes.byref(data), ctypes.byref(item))
        value = None
        try:
            if status == 0 and data.value: value = ctypes.string_at(data, length.value).decode()
        finally:
            if data.value: self.security.SecKeychainItemFreeContent(None, data)
        return status, value, item

    def _quiet(self, action):
        old = ctypes.c_ubyte(1)
        self.security.SecKeychainGetUserInteractionAllowed(ctypes.byref(old))
        self.security.SecKeychainSetUserInteractionAllowed(0)
        try: return action()
        finally: self.security.SecKeychainSetUserInteractionAllowed(old)

    def get(self):
        if self.value: return self.value
        def read():
            status, value, item = self._query()
            if item.value: self.cf.CFRelease(item)
            if status == 0: self.value = value; self.storage = "keychain"
        try: self._quiet(read)
        except (OSError, ValueError): pass
        return self.value

    def set(self, value):
        self.value = value; raw = value.encode(); self.storage = "memory"
        def write():
            status, _, item = self._query()
            try:
                if status == 0 and item.value:
                    code = self.security.SecKeychainItemModifyAttributesAndData(item, None, len(raw), raw)
                elif status == -25300:
                    code = self.security.SecKeychainAddGenericPassword(None, len(self.service), self.service, len(self.account), self.account, len(raw), raw, None)
                else: return
                if code == 0: self.storage = "keychain"
            finally:
                if item.value: self.cf.CFRelease(item)
        try: self._quiet(write)
        except (OSError, ValueError): pass


def credential_vault(root):
    if sys.platform == 'darwin':
        try: return MacKeychainVault(root)
        except OSError: pass
    return MemoryVault(root)
