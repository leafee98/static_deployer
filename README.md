# Static Deplyer

A simple daemon help with extracting tar files to specific place
and create a symbolic link to it, the tar files should be transferred
to this daemon by http.

## Caution

No `data-form` or `x-www-urlencoded-form` supported, so the tar must be transferred
just in POST body, ie: `curl --data-binary @file.tar.gz`.

No authorization implemented, so a reverse proxy with auth is recommanded.

Tar file with sub directories with be extracted as is, so do not contain parent
directory when you create tar.

## Usage

```
$ ./main.py --help
usage: main.py [-h] --archive-dir ARCHIVE_DIR --extract-dir EXTRACT_DIR --symlink-path
               SYMLINK_PATH [--keep-extract KEEP_EXTRACT] [--keep-archive KEEP_ARCHIVE]
               --port PORT [--temp-dir TEMP_DIR]

options:
  -h, --help            show this help message and exit
  --archive-dir ARCHIVE_DIR
                        directory to save archives
  --extract-dir EXTRACT_DIR
                        directory to save extracted files
  --symlink-path SYMLINK_PATH
                        path of symlink which redirect to extracted archive
  --keep-extract KEEP_EXTRACT
                        Number of extracted archives to keep, 0 mean never vacuum
  --keep-archive KEEP_ARCHIVE
                        Number of archives to keep, 0 mean never vacuum
  --port PORT           listen port on 127.0.0.1, no authorization implemented so only
                        listen on 127.0.0.1 for safety
  --temp-dir TEMP_DIR   path to save in-delivery archive
```

## Example

First start the daemon.

```
$ ./main.py --port 8080 --archive-dir archive --extract-dir extracted --symlink-path serve
INFO:root:Listening on 127.0.0.1:8080
INFO:root:Archive saves under: archive
INFO:root:Extract tar under: extracted
INFO:root:Keep 8 archives at most
INFO:root:Keep 4 extracted at most
INFO:root:Symbolic link location: serve
INFO:root:Temperory directory: /tmp
INFO:root:Starting httpd...
```

Then create a tar and upload it to this daemon.

**Note**: the tar shouldn't contain its parent directory, but `.` as parent
is acceptable. Or you can follow [this step](https://stackoverflow.com/a/39530409)
to create a more elegant tar.

```
$ mkdir tmp
$ cd tmp
$ echo 'Hello, world!' > index.html
$ tar --gzip -cf ../tmp.tar.gz .
$ tar -tf ../tmp.tar.gz
./
./index.html
$ curl --data-binary @../tmp.tar.gz http://localhost:8080/
Success
```

And the server side shows

```
...
INFO:root:Starting httpd...
INFO:FileManager:Temporarily save to /tmp/archive_2023-04-04T10:35:49.tar.gz
INFO:FileManager:Moving saved archive to archive/archive_2023-04-04T10:35:49.tar.gz
INFO:FileManager:Extracting to extracted/archive_2023-04-04T10:35:49
INFO:FileManager:Recreating symlink point to extracted/archive_2023-04-04T10:35:49
INFO:FileManager:Vacuuming archive, keep the 8 lastest
INFO:FileManager:Vacuuming extract, keep the 4 lastest
INFO:FileManager:Deploy success
127.0.0.1 - - [04/Apr/2023 10:35:49] "POST / HTTP/1.1" 200 -
```

Finally the directory looks like (omit unrelated directories):

```
.
├── archive
│   └── archive_2023-04-04T10:35:49.tar.gz
├── extracted
│   └── archive_2023-04-04T10:35:49
│       └── index.html
└── serve -> extracted/archive_2023-04-04T10:35:49
```

## Use Case

When you hold a static site and want to update its content easily,
like just uploading a tar and automatically deployed.
