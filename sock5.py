#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from gevent import monkey
    monkey.patch_all()
except:
    print 'Import gevent failed!'

import SocketServer
import struct
import logging
import socket
import select
import errno
import threading

#Commands
CMD_CONNECT = 1

#Address type
ADTY_IPV4 = 1
ADTY_DOMAIN = 3
ADTY_IPV6 = 4

#Reply field
REP_SUCCEEDED = 0
REP_SERVER_FAILURE = 1
REP_CONN_NOT_ALLOWED = 2
REP_NETWORD_UNREACHABLE = 3
REP_HOST_UNREACHABLE = 4
REP_CONN_REFUSED = 5
REP_TTL_EXPIRED = 6
REP_CMD_NOT_SUPPORTED = 7
REP_ADTY_NOT_SUPPORTED = 8
REP_UNASSIGNED = 9

class YXSock5Exception(Exception):
    pass

class LocalServer(SocketServer.StreamRequestHandler):
    def reply(self, rep):
        reply = '\x05' + struct.pack('>B', rep) + '\x00\x01'
        reply += socket.inet_aton('0.0.0.0') + struct.pack('>H', 33445)
        self.wfile.write(reply)

    def handle(self):
        try:
            self.request.recv(260) #acturally 2+255
            self.request.send('\x05\x00')
            req = self.rfile.read(4)
            cmd = ord(req[1])
            if cmd != CMD_CONNECT: #connection
                logging.warn("CMD 0x%x not supported!", cmd)
                self.reply(REP_CMD_NOT_SUPPORTED)
                return
            addrtype = ord(req[3])
            if addrtype == ADTY_IPV4:
                addr_ip = self.rfile.read(4)
                addr = socket.inet_ntoa(addr_ip)
            elif addrtype == ADTY_DOMAIN:
                addr_len = self.rfile.read(1)
                addr = self.rfile.read(ord(addr_len))
            else:
                logging.warn("ATYP 0x%x not supported!", addrtype)
                self.reply(REP_ADTY_NOT_SUPPORTED)
                return
            port = struct.unpack('>H', self.rfile.read(2))[0]
            try:
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
                remote.connect((addr, port))
            except socket.error, e:
                if e.errno == errno.ECONNREFUSED:
                    self.reply(REP_CONN_REFUSED)
                elif e.errno == errno.ENETUNREACH:
                    self.reply(REP_NETWORD_UNREACHABLE)
                elif e.errno == errno.EHOSTUNREACH:
                    self.reply(REP_HOST_UNREACHABLE)
                raise
            self.reply(REP_SUCCEEDED)
            self.forward_sockets(self.request, remote)
        except Exception, e:
            logging.warn(e)

    def forward_sockets(self, local, remote):
        fdset = [local, remote]
        try:
            while True:
                r, w, e = select.select(fdset, [], [])
                if local in r:
                    if remote.send(local.recv(4096)) <= 0:
                        break
                if remote in r:
                    if local.send(remote.recv(4096)) <= 0:
                        break
        finally:
            remote.close()

if __name__ == '__main__':
    import sys, daemon
    logging.basicConfig(filename='/var/log/yxsock5.log')
    daemon.daemonize()
    daemon.create_pid_file('yxsock5')
    def _():
        server = SocketServer.ThreadingTCPServer(('0.0.0.0', 8089), LocalServer)
        server.allow_reuse_address = True
        #server.serve_forever()
        t = threading.Thread(target=server.serve_forever)
        t.setDaemon(True)
        t.start()
        t.join()
    _()
