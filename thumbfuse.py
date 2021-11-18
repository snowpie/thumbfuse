#!/usr/bin/env python3

from __future__ import with_statement

import os
import sys
import errno
import PIL
import glob
import re

from fuse import FUSE, FuseOSError, Operations
from PIL import Image



class Passthrough(Operations):
    def __init__(self, root):
        self.root = root
        self.imageformats = [".jpg",".jpeg"]
        self.pattern = re.compile("^.scaled.[0-9]{0,5}.[0-9]{0,5}")

    # Helpers
    # =======

    def _full_path(self, partial):
        partial = partial.lstrip("/")
        if self._isscalepath(partial):
            partial=partial.split('/')[1:]
        path = os.path.join(self.root, partial)
        return path

    def _isscalepath(self,path):
        # if the path starts with .scaled.xxx.yyy/ then we scale any images beneath
        # to width=xxx height=yyy

        # are we in a scale path?

        # if so, write this.h , this.w after bounds checking

        # Return true or false acordingly
        ## [w,h]=_getscale(full_path)
        print("Checking path: "+ path)
        if (self.pattern.match(path)):
            print("Magic path: "+ path)
            return True
        return False
    def _stripscalepath(self,path):
        ## remove the .scaled.* bit if present
        return path


    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(self._stripscalepath(full_path, mode)):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        raise FuseOSError(errno.EROFS)
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        raise FuseOSError(errno.EROFS)
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        raise FuseOSError(errno.EROFS)
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        raise FuseOSError(errno.EROFS)
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        raise FuseOSError(errno.EROFS)
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        raise FuseOSError(errno.EROFS)
        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        raise FuseOSError(errno.EROFS)
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        raise FuseOSError(errno.EROFS)
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    # Mirror filesystem starts with .scaled.width.height , eg .scaled.600x800 . if either is blank, use the other one and scale uniformly
    def open(self, path, flags):
        full_path = self._full_path(path)
        width=800
        height=600
        print(os.path.splitext(full_path)[1].lower())
        if (self._isscalepath(path) and os.path.isfile(full_path) and os.path.splitext(full_path)[1].lower() in self.imageformats):
            print(full_path + " is an imagei to be scaled")

            img=Image.open(full_path)
            img.resize((width,height),PIL.Image.LANCZOS).save("/tmp/.scaled."+str(width)+"x"+str(height)+"test.jpg",quality=50)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        raise FuseOSError(errno.EROFS)
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        raise FuseOSError(errno.EROFS)
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        raise FuseOSError(errno.EROFS)
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)


def main(mountpoint, root):
    FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    if (len(sys.argv) != 3):
        sys.exit("Usage: "+sys.argv[0]+" targetfolder mountpoint")
    main(sys.argv[2], sys.argv[1])
