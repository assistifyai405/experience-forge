"""Run test controls with Python network connections denied; never infer a model."""
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

def deny_network(*args, **kwargs):
    raise AssertionError('Network connection attempted during offline tests')

with patch.object(socket.socket, 'connect', deny_network), patch.object(socket.socket, 'connect_ex', deny_network):
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
