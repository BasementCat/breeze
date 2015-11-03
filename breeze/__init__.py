import json
import re
import os
import sys
import SimpleHTTPServer
import SocketServer
import argparse
import logging
import fnmatch
from collections import OrderedDict


logger = logging.getLogger(__name__)


class NotRequirableError(Exception):
    pass


class Breeze(object):
    def __init__(self):
        self.context = {}
        self.files = OrderedDict()
        self.plugins = []
        self.once_plugins = []

    def run(self, args=None, exit=True):
        parser = argparse.ArgumentParser(description="Breeze CLI utility")
        parser.add_argument('command', metavar='command', help="Command to run", choices=['run', 'build'])
        parser.add_argument('-c', '--config', help='Configuration file to load from', default='config.json')
        parser.add_argument('-i', '--include', help='Include files and directories matching this pattern, recursively', action='append', default=['*'])
        parser.add_argument('-x', '--exclude', help='Exclude files and directories matching this pattern, recursively', action='append', default=[])
        parser.add_argument('-I', '--include-files', help='Include filenames matching this pattern', action='append', default=[])
        parser.add_argument('-X', '--exclude-files', help='Exclude filenames matching this pattern', action='append', default=['_*'])
        parser.add_argument('-s', '--source', help='Start at this directory location when looking for files', default='./')
        parser.add_argument('-d', '--destination', help='Put the final result into this directory, creating it if it does not exist and replacing it if it does', default='./_compiled')
        parser.add_argument('-p', '--port', help='For the run command, run on this port', default=8000, type=int)
        parser.add_argument('-D', '--debug', help='Debug level', action='count')

        args = args or sys.argv
        opts = parser.parse_args(args[1:])

        logging.basicConfig(level=[logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG][min(opts.debug or 0, 3)])

        old_dir = os.getcwd()
        os.chdir(os.path.dirname(args[0]))
        retcode = 0
        try:
            with open(opts.config, 'r') as fp:
                self.config = json.load(fp)

            self.config.update(vars(opts))
            self.config['exclude'] += [self.config['config'], os.path.join(old_dir, sys.argv[0])]
            for key in ('include', 'exclude'):
                self.config[key] = [os.path.realpath(os.path.abspath(v)) for v in self.config[key]]

            cmd = getattr(self, '_command_' + re.sub(ur'[^\w]', '', args[1].lower()))

            retcode = cmd() or 0
        except Exception as e:
            if exit:
                logger.critical('%s: %s', e.__class__.__name__, str(e), exc_info=True)
                retcode = 1
            else:
                raise
        finally:
            os.chdir(old_dir)

        if exit:
            sys.exit(retcode)
        return retcode

    def _command_run(self):
        try:
            logger.warning("This development server is for debugging purposes only and not intended to serve real traffic.")
            logger.info("Running development server on http://localhost:%d/", self.config['port'])
            SocketServer.TCPServer(
                ('', self.config['port']),
                SimpleHTTPServer.SimpleHTTPRequestHandler
            ).serve_forever()
        except KeyboardInterrupt:
            logger.debug("Exiting due to ctrl+c")

    def _command_build(self):
        self.build_filelist()
        self.run_plugins()
        print self.files
        print self.context

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
                    self.files[filename] = {'destination': filename}

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
            plugin.run(self)
