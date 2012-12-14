#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import atexit
import fcntl
import signal
import logging

DEFAULT_DEVNULL = os.devnull

def create_pid_file(name, path='/var/run/'):
    fpath = os.path.join(path, name+'.pid')
    try:
        fd = os.open(fpath, os.O_RDWR|os.O_CREAT, 0644)
        fcntl.lockf(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.ftruncate(fd, 0)
        os.write(fd, '%d' %os.getpid())
    except (IOError, OSError), e:
        logging.error("-- Programme running! %s", e.message)
        sys.exit(-1)
    def _():
        fcntl.lockf(fd, fcntl.LOCK_UN)
        os.unlink(fpath)
    atexit.register(_)

def daemonize(stdin=DEFAULT_DEVNULL, stdout=DEFAULT_DEVNULL, stderr=DEFAULT_DEVNULL):
    #not leader of PGRP
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError, e:
        logging.error("-- Fork failed! %s", e.message)
        sys.exit(-1)

    #no control terms, but become leader of PGRP
    os.chdir('/')
    os.setsid()

    #not leader of PGRP again
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError, e:
        logging.error("-- Fork failed! %s", e.message)
        sys.exit(-1)

    #dup STD I/Os
    try:
        si = open(stdin, 'r')
        so = open(stdout, 'a+')
        se = open(stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        del si, so, se
    except IOError, e:
        logging.error("-- Dup FDs failed! %s", e.message)
        sys.exit(-1)

    #handle signals, for atexit..
    def sighandler(signum, frame):
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
    signal.signal(signal.SIGTERM, sighandler)
    signal.signal(signal.SIGINT, sighandler)

if __name__=='__main__':
    import time
    def func():
        while True:
            print 'hello'
            time.sleep(3)
    daemonize(stdout='/tmp/dump', stderr='/tmp/dump')
    create_pid_file('daemont', '/tmp/')
