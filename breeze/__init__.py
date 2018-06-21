import time
import pprint
import shutil
import json
import re
import os
import sys
import traceback
try:
    import SimpleHTTPServer as httpserver
    import SocketServer as socketserver
except ImportError:
    import http.server as httpserver
    import socketserver
import argparse
import logging
import fnmatch
from collections import OrderedDict


logger = logging.getLogger(__name__)


class NotRequirableError(Exception):
    pass


class InDirectory(object):
    def __init__(self, directory, root=None):
        self.original_directory = None
        self.directory = directory
        if root:
            self.directory = os.path.join(root, self.directory)

    def __enter__(self):
        self.original_directory = os.getcwd()
        logger.debug("cd %s -> %s", self.original_directory, self.directory)
        os.chdir(self.directory)

    def __exit__(self, type, value, traceback):
        if self.original_directory and self.original_directory != os.getcwd():
            logger.debug("cd %s <- %s", self.original_directory, os.getcwd())
            os.chdir(self.original_directory)


class Breeze(object):
    def __init__(self):
        self._reset()
        self.plugins = []
        self.once_plugins = []
        self.debuglevel = logging.ERROR
        self.root_directory = None

    def _reset(self):
        self.context = {}
        self.files = OrderedDict()

    @classmethod
    def _compare(self, key, op, invert, test, data):
        value = data.get(key)
        out = False
        if op == 'eq':
            out = (value == test)
        elif op == 'ne':
            out = (value != test)
        elif op == 'lt':
            out = (value < test)
        elif op == 'lte':
            out = (value <= test)
        elif op == 'gt':
            out = (value > test)
        elif op == 'gte':
            out = (value >= test)
        elif op == 're':
            out = re.match(test, value)
        elif op == 'fn':
            out = fnmatch.fnmatch(value, test)
        else:
            raise ValueError("Invalid op: " + op)

        if invert:
            return False if out else True
        return True if out else False

    @classmethod
    def _compare_key(self, key, test, data):
        op = None
        invert = False
        if key.startswith('not__'):
            invert = True
            key = key[5:]
        if '__' in key:
            key, op = key.rsplit('__', 1)

        return self._compare(key, op or 'eq', invert, test, data)

    def filelist(self, pattern=None, **kwargs):
        for filename, file_data in self.files.items():
            if pattern and not fnmatch.fnmatch(filename, pattern):
                continue

            if kwargs:
                ok = True
                for key, test in kwargs.items():
                    if not self._compare_key(key, test, file_data):
                        ok = False
                        break
                if not ok:
                    continue

            yield (filename, file_data)

    def run(self, args=None, exit=True):
        parser = argparse.ArgumentParser(description="Breeze CLI utility")
        parser.add_argument('command', metavar='command', help="Command to run", choices=['run', 'build'])
        parser.add_argument('-c', '--config', help='Configuration file to load from', default='config.json')
        parser.add_argument('-i', '--include', help='Include files and directories matching this pattern, recursively', action='append', default=None)
        parser.add_argument('-x', '--exclude', help='Exclude files and directories matching this pattern, recursively', action='append', default=None)
        parser.add_argument('-I', '--include-files', help='Include filenames matching this pattern', action='append', default=None)
        parser.add_argument('-X', '--exclude-files', help='Exclude filenames matching this pattern', action='append', default=None)
        parser.add_argument('-s', '--source', help='Start at this directory location when looking for files', default=None)
        parser.add_argument('-d', '--destination', help='Put the final result into this directory, creating it if it does not exist and replacing it if it does', default=None)
        parser.add_argument('-p', '--port', help='For the run command, run on this port', type=int, default=None)
        parser.add_argument('-D', '--debug', help='Debug level', action='count', default=None)
        parser.add_argument('--build-interval', help='When using the run command, don\'t build more frequently than this (seconds)', default=None)

        self.config = {
            'include': ['*'],
            'exclude': [],
            'include_files': [],
            'exclude_files': ['_*'],
            'source': './',
            'destination': './_compiled',
            'port': 8000,
            'debug': 0,
            'build_interval': 2,
        }

        args = args or sys.argv
        opts = parser.parse_args(args[1:])

        self.debuglevel = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG][min(opts.debug or 0, 3)]
        logging.basicConfig(level=self.debuglevel)

        self.root_directory = os.path.abspath(os.path.dirname(args[0]))
        bin_file = os.path.relpath(os.path.abspath(args[0]), self.root_directory)

        with InDirectory(self.root_directory):
            retcode = 0
            try:
                with open(opts.config, 'r') as fp:
                    self.config.update(json.load(fp))

                self.config.update({k: v for k, v in vars(opts).items() if v is not None})
                self.config['exclude'] += [self.config['config'], bin_file, self.config['destination']]
                for key in ('include', 'exclude'):
                    self.config[key] = [os.path.realpath(os.path.abspath(v)) for v in self.config[key]]

                cmd = getattr(self, '_command_' + re.sub(r'[^\w]', '', args[1].lower()))

                retcode = cmd() or 0
            except Exception as e:
                if exit:
                    logger.critical('%s: %s', e.__class__.__name__, str(e), exc_info=True)
                    retcode = 1
                else:
                    raise

        if exit:
            sys.exit(retcode)
        return retcode

    def _command_run(self):
        try:
            logger.warning("This development server is for debugging purposes only and not intended to serve real traffic.")
            logger.info("Running development server on http://localhost:%d/", self.config['port'])

            _breeze_instance = self
            _breeze_instance._last_build = time.time() - 86400
            class _BuildingHandler(httpserver.SimpleHTTPRequestHandler):
                def do_GET(self, *args, **kwargs):
                    if time.time() - _breeze_instance._last_build >= _breeze_instance.config['build_interval']:
                        try:
                            _breeze_instance._command_build()
                            _breeze_instance._last_build = time.time()
                        except Exception as e:
                            self.send_response(500)
                            resp = traceback.format_exc()
                            self.send_header('Content-type', 'text/plain')
                            self.send_header('Content-length', len(resp))
                            self.send_header('Content-encoding', 'utf-8')
                            self.end_headers()
                            self.wfile.write(resp.encode('utf-8'))
                            self.wfile.flush()
                            return
                    return httpserver.SimpleHTTPRequestHandler.do_GET(self, *args, **kwargs)

            with InDirectory(self.config['destination'], self.root_directory):
                socketserver.TCPServer(
                    ('', self.config['port']),
                    _BuildingHandler,
                ).serve_forever()

        except KeyboardInterrupt:
            logger.debug("Exiting due to ctrl+c")

    def _command_build(self):
        self._reset()
        with InDirectory(self.root_directory):
            self.build_filelist()
            self.run_plugins()
            # if self.debuglevel == logging.DEBUG:
            #     print "--- FILES ---"
            #     pprint.pprint(dict(self.files), indent=4)
            #     print
            #     print "--- CONTEXT ---"
            #     pprint.pprint(dict(self.context), indent=4)
            #     print
            self.write_output()

    def build_filelist(self):
        queue = [self.config['source']]
        while queue:
            cur_dir = queue.pop()
            for filename in os.listdir(cur_dir):
                filename = os.path.abspath(os.path.realpath(os.path.join(cur_dir, filename)))
                # Default to false - if it's not in the include list, it's thrown out
                is_ok = False
                # Check against global include list
                for pattern in self.config['include']:
                    if fnmatch.fnmatch(filename, pattern):
                        is_ok = True
                        break
                # If it's on the include list, check against the exclude list
                if is_ok:
                    for pattern in self.config['exclude']:
                        if fnmatch.fnmatch(filename, pattern):
                            is_ok = False
                            break
                # Once a file has been excluded, don't check it anymore
                # But if it is still included, check the filename itself
                # This time in reverse - exclude first, then include
                if is_ok:
                    filename_basename = os.path.basename(filename)
                    for pattern in self.config['exclude_files']:
                        if fnmatch.fnmatch(filename_basename, pattern):
                            is_ok = False
                            break
                    # Now the include list may whitelist files previously excluded
                    if not is_ok:
                        for pattern in self.config['include_files']:
                            if fnmatch.fnmatch(filename_basename, pattern):
                                is_ok = True
                                break
                # Throw it out
                if not is_ok:
                    continue
                # Put it in the file list, or the queue
                if os.path.isdir(filename):
                    queue.append(filename)
                else:
                    filename = os.path.relpath(filename, os.path.realpath(os.path.abspath(self.config['source'])))
                    self.files[filename] = {'source': filename, 'destination': filename}

    def _plugin_require(self, plugin):
        for sub_plugin_class in plugin.requires():
            if not sub_plugin_class.requirable:
                raise NotRequirableError(
                    'Plugin "{}" required by "{}" cannot be required'.format(sub_plugin_class.__name__, plugin.__class__.__name__),
                    sub_plugin_class.__name__
                )
            self.plugin(sub_plugin_class())

    def plugin(self, plugin):
        try:
            self._plugin_require(plugin)
        except NotRequirableError as e:
            raise NotRequirableError(e[0], plugin.__class__.__name__, *e[1:])
        plugin_instance = plugin
        if type(plugin_instance) is type:
            plugin_instance = plugin_instance()
        if plugin_instance.run_once:
            if plugin_instance.__class__ in self.once_plugins:
                logger.warning('Plugin "%s" may only run once', plugin_instance.__class__.__name__)
                return self
            self.once_plugins.append(plugin_instance.__class__)
        self.plugins.append(plugin_instance)
        return self

    def run_plugins(self):
        for plugin in self.plugins:
            out = plugin.run(self)
            if out is not None:
                self.files = out

    def write_output(self):
        files = {os.path.join(self.config['destination'], v['destination']): v for v in self.files.values()}
        dirs = set([os.path.dirname(k) for k, v in files.items() if not v.get('skip_write')])

        try:
            shutil.rmtree(self.config['destination'])
        except OSError:
            if os.path.exists(self.config['destination']):
                raise

        for dirname in dirs:
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        for filename, file_data in files.items():
            if file_data.get('skip_write'):
                continue
            with open(filename, 'wb') as out_fp:
                contents = None
                if file_data.get('_contents') is not None:
                    if file_data.get('_mimetype') and file_data.get('_mimetype').startswith('text/'):
                        contents = file_data['_contents'].encode('utf-8')
                    else:
                        contents = file_data['_contents']
                out_fp.write(contents)
