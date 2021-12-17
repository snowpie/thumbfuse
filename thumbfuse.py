#!/usr/bin/env python3

from __future__ import with_statement

import os
import sys
import errno
import PIL
import glob
import re
import io

from fuse import FUSE, FuseOSError, Operations
from PIL import Image
from pymemcache.client import base
from random import randrange

memcacheclient = base.Client(('127.0.0.1', 11211))
loglevel=1


class Passthrough(Operations):
    def __init__(self, root):
        self.root = root
        self.imageformats = [".jpg",".jpeg",".png"]

    # Helpers
    # =======

    def debug(self,log,prio=1):
        if prio==loglevel:
            print(str(log)[0], end="")
            sys.stdout.flush()
        if prio>loglevel:
            print(log)

    def _full_path(self, partial):
        partial = partial.lstrip("/")
        path = os.path.join(self.root, partial)
        return path

    def image_to_byte_array(self,image:Image,full_path):
      fmt=os.path.splitext(full_path)[1].lower().lstrip(".")
      if fmt=="jpg":
          fmt="jpeg"
      imgByteArr = io.BytesIO()
      image.save(imgByteArr, format=fmt)
      #image.save(imgByteArr, format=image.format)
      #image.save(imgByteArr, format='jpeg')
      #imgByteArr = imgByteArr.getvalue()
      return imgByteArr

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
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
            dirlist=os.listdir(full_path)
            for entry in dirlist:
                if os.path.splitext(entry)[1].lower() in self.imageformats or os.path.isdir(full_path+"/"+entry):
                    dirents.append(entry)

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


    def open(self, path, flags):
        full_path = self._full_path(path)
        width=640
        height=480
        objkey=path.replace(" ","+") # +":"+str(width)+":"+str(height)).replace(" ","+")

        imagebytearray=memcacheclient.get(objkey)

        if imagebytearray is None:
            self.debug("MISS CACHED "+objkey)
            if (os.path.isfile(full_path) and os.path.splitext(full_path)[1].lower() in self.imageformats):
                self.debug("Scaling image "+full_path)

                img=Image.open(full_path)
                newimage=img.resize((width,height),PIL.Image.LANCZOS)
                #newimage=img.thumbnail((width,height),PIL.Image.LANCZOS)
                ## https://stackoverflow.com/questions/33101935/convert-pil-image-to-byte-array
                ## https://stackoverflow.com/questions/42800250/difference-between-open-and-io-bytesio-in-binary-streams
                ## https://docs.python.org/3/library/io.html
                imageIO=self.image_to_byte_array(newimage,full_path)
                imagebytearray=imageIO.getvalue()
                memcacheclient.set(objkey,imagebytearray)
        else:
            self.debug("HIT CACHE")
        return randrange(1,1000000)

    def create(self, path, mode, fi=None):
        raise FuseOSError(errno.EROFS)
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        self.debug(fh)
        imagebytearray=memcacheclient.get(path.replace(" ","+"))
        return imagebytearray[offset:(offset+length)]

    #    fh2 = io.BytesIO(imagebytearray)

    #    os.lseek(fh2, offset, os.SEEK_SET)
#        return os.read(fh, length)

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
        return 0
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)


def main(mountpoint, root, maxwidth, maxheight):
    FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    if (len(sys.argv) != 5):
        sys.exit("Usage: "+sys.argv[0]+" targetfolder mountpoint maxwidth maxheight")
    main(sys.argv[2], sys.argv[1], sys.argv[3], sys.argv[4])
