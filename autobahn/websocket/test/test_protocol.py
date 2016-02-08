###############################################################################
#
# The MIT License (MIT)
#
# Copyright (c) Tavendo GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
###############################################################################

from __future__ import absolute_import, print_function

from hashlib import sha1
from base64 import b64encode
import unittest2 as unittest

from autobahn.websocket.protocol import WebSocketServerProtocol
from autobahn.websocket.protocol import WebSocketServerFactory
from autobahn.websocket.protocol import WebSocketClientProtocol
from autobahn.websocket.protocol import WebSocketClientFactory
from autobahn.websocket.protocol import WebSocketProtocol
from autobahn.test import FakeTransport

from mock import Mock


class WebSocketClientProtocolTests(unittest.TestCase):

    def setUp(self):
        t = FakeTransport()
        f = WebSocketClientFactory()
        p = WebSocketClientProtocol()
        p.factory = f
        p.transport = t

        p._connectionMade()
        p.state = p.STATE_OPEN
        p.websocket_version = 18

        self.protocol = p
        self.transport = t

    def tearDown(self):
        for call in [
                self.protocol.autoPingPendingCall,
                self.protocol.autoPingTimeoutCall,
                self.protocol.openHandshakeTimeoutCall,
                self.protocol.closeHandshakeTimeoutCall,
        ]:
            if call is not None:
                call.cancel()

    def test_auto_ping(self):
        self.protocol.autoPingInterval = 1
        self.protocol.websocket_protocols = [Mock()]
        self.protocol.websocket_extensions = []
        self.protocol._onOpen = lambda: None
        self.protocol._wskey = '0' * 24
        self.protocol.peer = Mock()

        # usually provided by the Twisted or asyncio specific
        # subclass, but we're testing the parent here...
        self.protocol._onConnect = Mock()
        self.protocol._closeConnection = Mock()

        # set up a connection
        self.protocol.startHandshake()

        key = self.protocol.websocket_key + WebSocketProtocol._WS_MAGIC
        self.protocol.data = (
            b"HTTP/1.1 101 Switching Protocols\x0d\x0a"
            b"Upgrade: websocket\x0d\x0a"
            b"Connection: upgrade\x0d\x0a"
            b"Sec-Websocket-Accept: " + b64encode(sha1(key).digest()) + b"\x0d\x0a\x0d\x0a"
        )
        self.protocol.processHandshake()

        self.assertTrue(self.protocol.autoPingPendingCall is not None)


class WebSocketServerProtocolTests(unittest.TestCase):
    """
    Tests for autobahn.websocket.protocol.WebSocketProtocol.
    """
    def setUp(self):
        t = FakeTransport()
        f = WebSocketServerFactory()
        p = WebSocketServerProtocol()
        p.factory = f
        p.transport = t

        p._connectionMade()
        p.state = p.STATE_OPEN
        p.websocket_version = 18

        self.protocol = p
        self.transport = t

    def tearDown(self):
        for call in [
                self.protocol.autoPingPendingCall,
                self.protocol.autoPingTimeoutCall,
                self.protocol.openHandshakeTimeoutCall,
                self.protocol.closeHandshakeTimeoutCall,
        ]:
            if call is not None:
                call.cancel()

    def test_auto_ping(self):
        proto = Mock()
        self.protocol.autoPingInterval = 1
        self.protocol.websocket_protocols = [proto]
        self.protocol.websocket_extensions = []
        self.protocol._onOpen = lambda: None
        self.protocol._wskey = '0' * 24
        self.protocol.succeedHandshake(proto)

        self.assertTrue(self.protocol.autoPingPendingCall is not None)

    def test_sendClose_none(self):
        """
        sendClose with no code or reason works.
        """
        self.protocol.sendClose()

        # We closed properly
        self.assertEqual(self.transport._written, b"\x88\x00")
        self.assertEqual(self.protocol.state, self.protocol.STATE_CLOSING)

    def test_sendClose_str_reason(self):
        """
        sendClose with a str reason works.
        """
        self.protocol.sendClose(code=1000, reason="oh no")

        # We closed properly
        self.assertEqual(self.transport._written[2:], b"\x03\xe8oh no")
        self.assertEqual(self.protocol.state, self.protocol.STATE_CLOSING)

    def test_sendClose_unicode_reason(self):
        """
        sendClose with a unicode reason works.
        """
        self.protocol.sendClose(code=1000, reason=u"oh no")

        # We closed properly
        self.assertEqual(self.transport._written[2:], b"\x03\xe8oh no")
        self.assertEqual(self.protocol.state, self.protocol.STATE_CLOSING)

    def test_sendClose_toolong(self):
        """
        sendClose with a too-long reason will truncate it.
        """
        self.protocol.sendClose(code=1000, reason="abc" * 1000)

        # We closed properly
        self.assertEqual(self.transport._written[2:],
                         b"\x03\xe8" + (b"abc" * 41))
        self.assertEqual(self.protocol.state, self.protocol.STATE_CLOSING)

    def test_sendClose_reason_with_no_code(self):
        """
        Trying to sendClose with a reason but no code will raise an Exception.
        """
        with self.assertRaises(Exception) as e:
            self.protocol.sendClose(reason="abc")

        self.assertIn("close reason without close code", str(e.exception))

        # We shouldn't have closed
        self.assertEqual(self.transport._written, b"")
        self.assertEqual(self.protocol.state, self.protocol.STATE_OPEN)

    def test_sendClose_invalid_code_type(self):
        """
        Trying to sendClose with a non-int code will raise an Exception.
        """
        with self.assertRaises(Exception) as e:
            self.protocol.sendClose(code="134")

        self.assertIn("invalid type", str(e.exception))

        # We shouldn't have closed
        self.assertEqual(self.transport._written, b"")
        self.assertEqual(self.protocol.state, self.protocol.STATE_OPEN)

    def test_sendClose_invalid_code_value(self):
        """
        Trying to sendClose with a non-valid int code will raise an Exception.
        """
        with self.assertRaises(Exception) as e:
            self.protocol.sendClose(code=10)

        self.assertIn("invalid close code 10", str(e.exception))

        # We shouldn't have closed
        self.assertEqual(self.transport._written, b"")
        self.assertEqual(self.protocol.state, self.protocol.STATE_OPEN)
