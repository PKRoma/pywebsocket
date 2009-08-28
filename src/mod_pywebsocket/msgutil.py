# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Message related utilities.
"""


import Queue
import StringIO
import traceback
import threading


def send_message(conn, message):
    """Send message.

    Args:
        conn: mod_python.apache.mp_conn object.
        message: unicode string to send.
    """

    conn.write('\x00' + message.encode('utf-8') + '\xff')


def receive_message(conn):
    """Receive a Web Socket frame and return its payload as unicode string.

    Args:
        conn: mod_python.apache.mp_conn object.
    """

    while True:
        # Read 1 byte.
        # mp_conn.read will block if no bytes are available.
        # TODO: check if timeout is properly handled by either mod_python or
        # Apache HTTP Server.
        frame_type_str = conn.read(1)
        frame_type = ord(frame_type_str[0])
        if (frame_type & 0x80) == 0x80:
            # The payload length is specified in the frame.
            # Read and discard.
            length = _payload_length(conn)
            _receive_bytes(conn, length)
        else:
            # The payload is delimited with \xff.
            bytes = _read_until(conn, '\xff')
            message = bytes.decode('utf-8')
            if frame_type == 0x00:
                return message
            # Discard data of other types.


def _payload_length(conn):
    length = 0
    while True:
        b_str = conn.read(1)
        b = ord(b_str[0])
        length = length * 128 + (b & 0x7f)
        if (b & 0x80) == 0:
            break
    return length


def _receive_bytes(conn, length):
    bytes = ''
    while length > 0:
        new_bytes = conn.read(length)
        bytes += new_bytes
        length -= len(new_bytes)
    return bytes


def _read_until(conn, delim_char):
    bytes = ''
    while True:
        ch = conn.read(1)
        if ch == delim_char:
            break
        bytes += ch
    return bytes


class MessageReceiver(threading.Thread):
    """This class receives messages from the client.

    This class provides both synchronous and asynchronous ways to receive
    messages.
    """
    def __init__(self, conn, onmessage=None):
        """Construct an instance.

        Args:
            conn: mod_python.apache.mp_conn object.
            onmessage: a function to be called when a message is received.
                       Can be None.
        """
        threading.Thread.__init__(self)
        self._conn = conn
        self._queue = Queue.Queue()
        self._onmessage = onmessage
        self.setDaemon(True)
        self.start()

    def run(self):
        while True:
            message = receive_message(self._conn)
            if self._onmessage:
                self._onmessage(message)
            else:
                self._queue.put(message)

    def receive(self):
        """ Receive a message from the channel, blocking.

        Returns:
            message as a unicode string.
        """

        return self._queue.get()

    def receive_nowait(self):
        """ Receive a message from the channel, non-blocking.

        Returns:
            message as a unicode string if available. None otherwise.
        """
        try:
            message = self._queue.get_nowait()
        except Queue.Empty:
            message = None
        return message


class MessageSender(threading.Thread):
    """This class sends messages to the client.

    This class provides both synchronous and asynchronous ways to send
    messages.
    """
    def __init__(self, conn):
        """Construct an instance.

        Args:
            conn: mod_python.apache.mp_conn object.
        """
        threading.Thread.__init__(self)
        self._conn = conn
        self._queue = Queue.Queue()
        self.setDaemon(True)
        self.start()

    def run(self):
        while True:
            message = self._queue.get()
            send_message(self._conn, message)

    def send(self, message):
        """Send a message, blocking."""

        send_message(self._conn, message)

    def send_nowait(self, message):
        """Send a message, non-blocking."""

        self._queue.put(message)


# vi:sts=4 sw=4 et
