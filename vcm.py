#!/usr/bin/env python
import click
import os
import ConfigParser
from string import strip
from subprocess import call
import subprocess
from urlparse import urlparse
import re

GLOBAL_CONFIG_LOCATION = '~/.vcm'
DEFAULT_NMAP_SETTINGS = ["-sV", "-p-"]

global_settings = None


# TODO: Main List
# Stuff to automate later:
# * brew install testssl
# * download openssl binary and store it in default location
# * brew install nmap
# * brew install nikto

class VcmGlobalConfig:

    open_ssl_binary = 'openssl'  # default - can be overridden in global config file.

    def __init__(self):
        pass

    def read_global_vcm(self):
        print "Reading global config from %s" % GLOBAL_CONFIG_LOCATION

        read_config = ConfigParser.RawConfigParser()
        global_config_filename = os.path.expanduser(GLOBAL_CONFIG_LOCATION)
        read_config.read(global_config_filename)

        self.open_ssl_binary = read_config.get('GlobalSettings', 'openssl_binary')

    def create_global_vcm(self):
        print "Creating global config file with defaults in %s" % GLOBAL_CONFIG_LOCATION
        global_config = ConfigParser.RawConfigParser()
        global_config.add_section('GlobalSettings')

        global_config.set('GlobalSettings', 'openssl_binary', self.open_ssl_binary)

        global_config_file = os.path.expanduser(GLOBAL_CONFIG_LOCATION)

        with open(global_config_file, 'wb') as configfile:
            try:
                global_config.write(configfile)
            except Exception as ex:
                print "Error writing config file: %s : %s" % (global_config_file, ex.strerror)
                return


class VcmProjectConfig:
    local_folder = ''
    remote_folder = ''
    project_name = ''
    targets = []

    def __init__(self):
        read_config = ConfigParser.RawConfigParser()

        cf = read_config.read('.vcm')

        if len(cf) == 0:
            raise Exception("Unable to read config file: %s" % os.path.join(os.getcwd(), '.vcm'))

        self.remote_folder = read_config.get('ProjectSettings', 'remote_path')
        self.local_folder = read_config.get('ProjectSettings', 'local_path')

        url_targets = re.split(",", read_config.get('ProjectSettings', 'url_targets'))

        for t in url_targets:
            self.targets.append(strip(t))


@click.group()
def vcm():
    global global_settings
    global_settings = VcmGlobalConfig()

    if os.path.isfile(os.path.expanduser(GLOBAL_CONFIG_LOCATION)):
        global_settings.read_global_vcm()
    else:
        global_settings.create_global_vcm()


###
#   Folder and project management
###
def create_folder(folder):
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception as ex:
            print "Error creating folder: %s : %s" % (folder, ex.strerror)
            return


@vcm.command()
def create():
    # create a config file .vcm and ask for: project name, root dir name, remote directory, urls (csv)
    project_name = click.prompt('Project Name', type=str)
    local_folder = click.prompt('Local Path', type=str, default=os.path.join(os.getcwd(), project_name))
    remote_folder = click.prompt('Remote Path', type=str)
    url_targets = click.prompt('URL Targets (CSV)', type=str)

    create_folder(local_folder)

    for folder in ['reports', 'artifacts', 'logistics']:
        create_folder(os.path.join(local_folder, folder))

    # write config file to .vcm in the root
    project_config = ConfigParser.RawConfigParser()
    project_config.add_section('ProjectSettings')
    project_config.set('ProjectSettings', 'project_name', project_name)
    project_config.set('ProjectSettings', 'local_path', os.path.join(local_folder, ''))
    project_config.set('ProjectSettings', 'remote_path', os.path.join(remote_folder, ''))
    project_config.set('ProjectSettings', 'url_targets', url_targets)
    with open(os.path.join(local_folder, '.vcm'), 'wb') as configfile:
        try:
            project_config.write(configfile)
        except Exception as ex:
            print "Error writing config file: %s : %s" % (os.path.join(local_folder, '.vcm'), ex.strerror)
            return


@vcm.command()
def push():
    # ensure the remote dir is mounted
    project_config = VcmProjectConfig()

    # do an rsync -ah from local to remote
    if click.confirm('Sync local (%s) to remote (%s)?' % (project_config.local_folder, project_config.remote_folder)):
        args = ["rsync", "-ah", "--progress", project_config.local_folder, project_config.remote_folder]
        call(args)


@vcm.command()
def pull():
    # ensure the remote dir is mounted
    # do an rsync -ah from remote to local
    project_config = VcmProjectConfig()

    # do an rsync -ah from local to remote
    if click.confirm('Sync remote (%s) to local (%s)?' % (project_config.remote_folder, project_config.local_folder)):
        args = ["rsync", "-ah", "--progress", project_config.remote_folder, project_config.local_folder]
        call(args)


###
#   Running testing tools
###
@vcm.group()
def run():
    pass


@run.command()
def nmap():
    # check if url .vcm setting is set and is valid csv first; strip protocol if exists
    project_config = VcmProjectConfig()

    nmap_targets = []
    for t in project_config.targets:
        nmap_targets.append(urlparse(t).netloc)

    print "Please note, this will only work if the url targets have been set to a comma delimited set of URLs with " \
          "scheme. "

    if click.confirm('Run nmap against the following targets: %s' % ', '.join(nmap_targets)):
        args = ["nmap"]
        args.extend(DEFAULT_NMAP_SETTINGS)

        for t in nmap_targets:
            args.append(t)

        args.append("-oA")
        args.append(os.path.join(project_config.local_folder, 'artifacts', 'nmap'))
        call(args)
    else:
        pass


# TODO FIX THIS TO ITERATE OVER URLS LIKE DIRB DOES
@run.command()
def nikto():
    # check if url .vcm setting is set and is valid csv first
    project_config = VcmProjectConfig()

    print "Please note, this will only work if the url targets have been set to a comma delimited set of URLs with " \
          "scheme. "

    if click.confirm('Run nikto against the following targets: %s' % ', '.join(project_config.targets)):
        try:
            # nikto -h https://www.test.com -ssl -Format html -output .
            filename = os.path.join(project_config.local_folder, 'artifacts', 'nikto')
            args = ["nikto", "-h"]

            for t in project_config.targets:
                args.append(t + ',')

            args.append('-ssl')
            args.append('-Format')
            args.append('html')
            args.append('-output')
            args.append(os.path.join(project_config.local_folder, 'artifacts', 'nikto'))

            print args
            call(args)
        except Exception as ex:
            print "Error writing nikto output to: %s : %s" % (filename, ex.strerror)
    else:
        pass


@run.command()
def testssl():
    # check if url .vcm setting is set and is valid csv first
    project_config = VcmProjectConfig()

    https_targets = []
    for t in project_config.targets:
        https_targets.append('https://' + urlparse(t).netloc)

    print "Please note, this will only work if the url targets have been set to a comma delimited set of URLs with " \
          "scheme. "

    if click.confirm('Run testssl against the following targets: %s' % ', '.join(https_targets)):
        for t in https_targets:
            try:
                filename = os.path.join(project_config.local_folder, 'artifacts',
                                        'testssl_' + str(https_targets.index(t))) + '.html'

                with open(filename, 'w') as f:
                    args_testssl = ["testssl.sh", "--openssl", global_settings.open_ssl_binary, t]
                    testssl_process = subprocess.Popen(args_testssl, stdout=subprocess.PIPE)
                    aha = subprocess.Popen(["aha"], stdin=testssl_process.stdout, stdout=f)
                    aha.wait()

            except Exception as ex:
                print "Error writing testssl output to: %s: %s" % (filename, ex.strerror)
    else:
        pass


@run.command()
def dirb():
    # check if url .vcm setting is set and is valid csv first
    project_config = VcmProjectConfig()

    print "Please note, this will only work if the url targets have been set to a comma delimited set of URLs with " \
          "scheme. "

    if click.confirm('Run dirb against the following targets: %s' % ', '.join(project_config.targets)):
        for t in project_config.targets:
            try:
                # dirb url -o output.txt
                dirb_filename = os.path.join(project_config.local_folder, 'artifacts',
                                             'dirb_' + str(project_config.targets.index(t))) + '.txt'
                args = ["dirb", t, '-o', dirb_filename]
                call(args)
            except Exception as ex:
                print "Error writing dirb output to: %s" % (dirb_filename, ex.strerror)
    else:
        pass


if __name__ == '__main__':
    vcm()
