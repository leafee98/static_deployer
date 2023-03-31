#!/usr/bin/env python3

"""
This Listen a port on 127.0.0.1 or [::1], (so no authorization
implement required), receive a .tar.gz file and extract it to
a specific path, and make it a soft link to the extracted files.

Use the following command to upload the file content:
curl -H "Content-Type: application/octet-stream" --data-binary @main.py http://localhost:8080

The file content must be a legal .tar.gz file. There must not be
a subdirectory to contain other files
"""

import os
import tarfile
import shutil
from pathlib import Path
from typing import BinaryIO, Union
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import argparse
import logging

class NotSymlinkException(Exception):
    pass
class NotDirectoryException(Exception):
    pass

class FileManager:
    logger = logging.getLogger("FileManager")

    archive_ext = ".tar.gz"

    def __init__(self, archive_dir: str, extract_dir: str, symlink_path: str,
                 keep_archive: int, keep_extract: int, temp_dir: str = "/tmp"):
        self.archive_dir = archive_dir
        self.extract_dir = extract_dir
        self.symlink_path = symlink_path

        self.keep_archive = keep_archive
        self.keep_extract = keep_extract

        self.temp_dir = temp_dir

        self._check_dirs()

    def _check_dirs(self):
        def check_dir(path):
            p = Path(path)
            if p.exists():
                if not p.is_dir():
                    raise NotDirectoryException("{} exists and is not a directory".format(path))
            else:
                os.makedirs(path)

        def check_symlink(path):
            p = Path(path)
            if p.exists():
                if not p.is_symlink():
                    raise NotSymlinkException("{} exists and is not a symlink".format(path))
            else:
                check_dir(os.path.dirname(path))

        check_dir(self.archive_dir)
        check_dir(self.extract_dir)
        check_dir(self.temp_dir)
        check_symlink(self.symlink_path)

    def _get_archive_name(self) -> str:
        time_str = datetime.now().isoformat(timespec="seconds")
        return f"archive_{time_str}{self.archive_ext}"

    def _get_basename(self, filename: str) -> str:
        if filename.endswith(self.archive_ext):
            return filename[:-len(self.archive_ext)]
        return filename

    def _extract(self, archive_path: str, target_path: str) -> bool:
        try:
            with tarfile.open(archive_path, mode="r:gz") as tf:
                tf.extractall(target_path)
        except Exception as e:
            self.logger.error("Failed to extract tar file: {}".format(e))
            return False
        return True


    def save_file(self, src: BinaryIO, content_length: int) -> Union[str, None]:
        archive_name = self._get_archive_name()
        tgt_file = os.path.join(self.temp_dir, archive_name)

        self.logger.info("Temporarily save to {}".format(tgt_file))

        try:
            f = open(tgt_file, "bw")
            redirect_stream(src, f, content_length)
            f.close()
        except:
            os.remove(tgt_file)
            return None

        final_file = os.path.join(self.archive_dir, archive_name)
        self.logger.info("Moving saved archive to {}".format(final_file))
        shutil.move(tgt_file, final_file)
        return final_file

    def deploy(self, archive_path: str) -> bool:
        extract_dir = os.path.join(self.extract_dir,
                                   self._get_basename(os.path.basename(archive_path)))

        self.logger.info("Extracting to {}".format(extract_dir))

        os.mkdir(extract_dir)
        if not self._extract(archive_path, extract_dir):
            self.logger.error("Failed to extract archive {} to {}"
                              .format(archive_path, extract_dir))
            return False

        self.logger.info("Recreating symlink point to {}".format(extract_dir))
        os.remove(self.symlink_path)
        os.symlink(extract_dir, self.symlink_path)

        return True

    def _vacuum_single(self, dirname: str, keep_count: int, rm_dir: bool) -> None:
        files = os.listdir(dirname)
        files.sort()
        for f in files[:-keep_count]:
            full_path = os.path.join(dirname, f)

            self.logger.info("Removing {}".format(full_path))
            if rm_dir:
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)

    def vacuum(self) -> None:
        if self.keep_archive > 0:
            self.logger.info("Vacuuming archive, keep the {} lastest".format(self.keep_archive))
            self._vacuum_single(self.archive_dir, self.keep_archive, False)
        if self.keep_extract > 0:
            self.logger.info("Vacuuming extract, keep the {} lastest".format(self.keep_extract))
            self._vacuum_single(self.extract_dir, self.keep_extract, True)

    def handle(self, instream: BinaryIO, content_length: int) -> bool:
        archive_path = self.save_file(instream, content_length)
        if archive_path is None:
            self.logger.error("Failed to save file. Aborted!")
            return False

        if not self.deploy(archive_path):
            self.logger.error("Failed to extract or create symlink. Aborted!")
            return False
        self.vacuum()
        self.logger.info("Deploy success")
        return True

global_mgr: FileManager


def redirect_stream(src: BinaryIO, tgt: BinaryIO, size: int) -> None:
    block_size = 4 * 1024 * 1024    # 4MB

    cache = src.read(size % block_size)
    tgt.write(cache)
    size -= size % block_size

    while size > 0:
        cache = src.read(block_size)
        tgt.write(cache)
        size -= block_size


class S(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    logger = logging.getLogger("HttpHandler")

    def __init__(self, *args, **kwargs):
        super(S, self).__init__(*args, **kwargs)

    def _set_response(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plaintext")
        self.end_headers()

    def do_GET(self):
        self.logger.info("Received GET request, Path: %s", str(self.path))
        content = "Non-implemented".encode("utf-8")
        self._write_response(403, "text/plaintext", content)

    def _write_response(self, status_code: int, content_type: str, content: bytes):
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()

            self.wfile.write(content)

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        if global_mgr.handle(self.rfile, content_length):
            content = "Success".encode("utf-8")
            self._write_response(200, "text/plaintext", content)
        else:
            content = "Failed".encode("utf-8")
            self._write_response(200, "text/plaintext", content)
        self.wfile.flush()


def run(archive_dir: str, extract_dir: str, symlink_path: str,
        keep_archive: int, keep_extract: int,
        port: int = 8080, temp_dir: str = "/tmp"):
    logging.basicConfig(level=logging.DEBUG)

    address = "127.0.0.1"

    logging.info("Listening on {}:{}".format(address, port))
    logging.info("Archive saves under: {}".format(archive_dir))
    logging.info("Extract tar under: {}".format(extract_dir))
    logging.info("Keep {} archives at most".format(keep_archive))
    logging.info("Keep {} extracted at most".format(keep_extract))
    logging.info("Symbolic link location: {}".format(symlink_path))
    logging.info("Temperory directory: {}".format(temp_dir))

    global global_mgr
    global_mgr = FileManager(archive_dir=archive_dir, extract_dir=extract_dir,
                             symlink_path=symlink_path, temp_dir=temp_dir,
                             keep_archive=keep_archive, keep_extract=keep_extract)

    httpd = HTTPServer((address, port), S)
    logging.info("Starting httpd...")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()
    logging.info("Stopping httpd...")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir",  dest="archive_dir",  type=str,
                    required=True, help="directory to save archives")
    ap.add_argument("--extract-dir",  dest="extract_dir",  type=str,
                    required=True, help="directory to save extracted files")
    ap.add_argument("--symlink-path", dest="symlink_path", type=str,
                    required=True, help="path of symlink which redirect to extracted archive")

    ap.add_argument("--keep-extract",  dest="keep_extract",  type=int,
                    default=4, help="Number of extracted archives to keep, 0 mean never vacuum")
    ap.add_argument("--keep-archive",  dest="keep_archive",  type=int,
                    default=8, help="Number of archives to keep, 0 mean never vacuum")

    ap.add_argument("--port",         dest="port",         type=int,
                    required=True, help="listen port on 127.0.0.1, " +
                    "no authorization implemented so only listen on 127.0.0.1 for safety")
    ap.add_argument("--temp-dir",     dest="temp_dir",     type=str,
                    default="/tmp", help="path to save in-delivery archive")

    args = ap.parse_args()

    run(archive_dir=args.archive_dir,
        extract_dir=args.extract_dir,
        symlink_path=args.symlink_path,
        keep_archive=args.keep_archive,
        keep_extract=args.keep_extract,
        temp_dir=args.temp_dir,
        port=args.port)
