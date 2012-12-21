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

def parse_args():
    import argparse
    #parse args
    parser = argparse.ArgumentParser(description='Run yxsock5 server.', prog='yxsock5')
    parser.add_argument('-f', dest='config_file', nargs='?', help='Load from a configuration file.')
    parser.add_argument('-P', dest='pid_file', nargs='?', help='Set file path for the pid file.', default='/var/run/yxsock5.pid')
    parser.add_argument('-L', dest='log_file', nargs='?', help='Set file path for the log file.', default='/var/log/yxsock5.pid')
    parser.add_argument('-a', dest='addr', nargs='?', help='Set the listening address.', default='0.0.0.0')
    parser.add_argument('-p', dest='port', nargs='?', help='Set the listening address.', default=8089, type=int)
    parser.add_argument('-d', dest='daemon', action='store_true', help='Launch as daemon.')
    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    pidfile = args.pid_file
    logfile = args.log_file
    addr = args.addr
    port = args.port
    dae = args.daemon
    if args.config_file:
        with open(args.config_file, 'r') as f:
            import json
            config = f.read()
            tmp = json.loads(config)
            pidfile = tmp['pid_file'] if 'pid_file' in tmp else pidfile
            logfile = tmp['log_file'] if 'log_file' in tmp else logfile
            addr = tmp['listen_addr'] if 'listen_addr' in tmp else addr
            port = tmp['listen_port'] if 'listen_port' in tmp else port
            dae = tmp['daemon'] if 'daemon' in tmp else dae
    #set up logging
    logging.basicConfig(filename=logfile, level=logging.WARNING)
    #create daemon
    import daemon
    if dae:
        daemon.daemonize()
    daemon.create_pid_file(pidfile)
    #create server
    server = SocketServer.ThreadingTCPServer((addr, port), LocalServer)
    server.allow_reuse_address = True
    t = threading.Thread(target=server.serve_forever)
    t.setDaemon(True)
    t.start()
    t.join()

if __name__ == '__main__':
    main()
