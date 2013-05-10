'''Clustering plugin (designed to sysadmin-toolkit)

The clustering plugin provides a few commands to ensure important files
and command output in the cluster are symmetric.

This plugin provides a clustering service for other plugins.

Run "debug commandprompt" for a list of available commands for this plugin,
or "debug clustering" for a list of configured elements.

Main website:
    https://github.com/lpther/Clustering

'''

__version__ = '0.1.0'

import ClusterShell
import ClusterShell.Task
import sysadmintoolkit
import logging

ALLOWED_SYMMETRIC_FILES_DIRECTIVES = ['recursive']

global plugin_instance

plugin_instance = None


def get_plugin(logger, config):
    '''
    '''
    global plugin_instance

    if plugin_instance is None:
        plugin_instance = Clustering(logger, config)

    return plugin_instance


class Clustering(sysadmintoolkit.plugin.Plugin):
    def __init__(self, logger, config):
        super(Clustering, self).__init__('clustering', logger, config)

        self.nodesets = {}
        self.reachable_nodes = {}
        if 'default-nodeset' in config:
            self.nodesets['default'] = ClusterShell.NodeSet.NodeSet(config['default-nodeset'])
        else:
            self.nodesets['default'] = ClusterShell.NodeSet.NodeSet.fromall()

        self.symmetric_files = {}
        if 'symmetric-files' in config:
            self.register_symmetric_files()

        self.symmetric_commands = {}
        if 'symmetric-commands' in config:
            self.register_symmetric_commands()

        self.task_connect_timeout = 3
        self.start_task()

        self.add_command(sysadmintoolkit.command.ExecCommand('debug clustering', self, self.debug))
        self.add_command(sysadmintoolkit.command.ExecCommand('show cluster symmetric-files', self, self.display_symmetric_files))
        self.add_command(sysadmintoolkit.command.ExecCommand('show cluster symmetric-files group <nodeset>', self, self.display_symmetric_files))
        self.add_command(sysadmintoolkit.command.ExecCommand('show cluster symmetric-commands', self, self.display_symmetric_commands))
        self.add_command(sysadmintoolkit.command.ExecCommand('show cluster symmetric-commands group <nodeset>', self, self.display_symmetric_commands))

        self.add_dynamic_keyword_fn('<nodeset>', self.get_nodesets)

        self.logger.debug('Clustering plugin started with default nodes: %s' % self.nodesets['default'])

    def start_task(self):
        '''
        Starts the clustershell task for file copy or shell commands dispatch to the cluster
        '''
        self.clustershell_task = ClusterShell.Task.task_self()
        self.clustershell_task.set_info('connect_timeout', self.task_connect_timeout)
        self.clustershell_task.set_info('fanout', 512)

        if self.logger.getEffectiveLevel() is logging.DEBUG:

            def log_debug(task, msg):
                self.logger.debug('Clustershell task %s: %s' % (task, msg))

            self.clustershell_task.set_info('debug', True)
            self.clustershell_task.set_info('print_debug', log_debug)

    def register_symmetric_files(self):
        '''
        Loads the symmetric files from the config argument at instantiation
        '''
        for entry in self.config['symmetric-files'].split(','):
            if entry is '':
                continue

            if ':' in entry:
                group = entry.strip().split(':')[0]
                sym_file = ':'.join(entry.strip().split(':')[1:])
            else:
                group = 'default'
                sym_file = entry.strip()

            directives = []
            if '|' in sym_file:
                directives_dict = {}
                for directive in sym_file.split('|')[0].split(','):
                    if directive in ALLOWED_SYMMETRIC_FILES_DIRECTIVES:
                        directives_dict[directive] = None
                    else:
                        self.logger.warning('Invalid directive in entry %s' % entry.strip())

                directives = directives_dict.keys()
                directives.sort()

                sym_file = sym_file.split('|')[1]

            if group is '' or '/' in group or not group.startswith('@'):
                group = 'default'
            else:
                group_nodeset = ClusterShell.NodeSet.NodeSet(group)

                if group not in self.nodesets:
                    if not self.register_nodes(group, group):
                        continue

            if group not in self.symmetric_files:
                self.symmetric_files[group] = {}

            self.logger.debug('Adding symmetric file "%s" to group %s' % (sym_file, group))

            self.symmetric_files[group][sym_file] = directives

    def register_symmetric_commands(self):
        '''
        Loads the symmetric commands from the config argument at instantiation
        '''
        for entry in self.config['symmetric-commands'].split(','):
            if entry is '':
                continue

            if ':' in entry:
                group = entry.strip().split(':')[0]
                command = ':'.join(entry.strip().split(':')[1:])
            else:
                group = 'default'
                command = entry.strip()

            command = command.replace('\;', ';')

            if group is '' or '/' in group or not group.startswith('@'):
                group = 'default'
            else:
                group_nodeset = ClusterShell.NodeSet.NodeSet(group)

                if group not in self.nodesets:
                    if not self.register_nodes(group, group):
                        continue

            if group not in self.symmetric_commands:
                self.symmetric_commands[group] = []

            self.logger.debug('Adding symmetric command "%s" to group %s' % (command, group))

            self.symmetric_commands[group].append(command)
            self.symmetric_commands[group].sort()

    def register_nodes(self, setname, nodes):
        '''
        Used by other plugins to register nodesets
        '''
        if setname in self.nodesets:
            return

        self.logger.debug('Registering nodeset named %s with nodes %s' % (setname, nodes))

        newnodeset = ClusterShell.NodeSet.NodeSet(nodes)

        if len(newnodeset) is 0:
            self.logger.warning('Node entry %s could not be resolved . Is it defined in the clustershell groups file?' % setname)
            return False
        else:
            self.nodesets[setname] = newnodeset
            return True


    def test_reachability(self, nodeset='default'):
        '''
        Simple test to ensure nodes are reachable
        '''
        self.clustershell_task.shell('echo CONNECTED', nodes=self.nodesets[nodeset])
        self.clustershell_task.resume()

        reachable_nodes = []

        for buf , nodes in self.clustershell_task.iter_buffers() :
            if 'CONNECTED' in buf:
                for reachable_node in nodes:
                    reachable_nodes.append(reachable_node)

        self.reachable_nodes[nodeset] = ClusterShell.NodeSet.NodeSet(','.join(reachable_nodes))

    def leave_mode(self, cmdprompt):
        '''
        Kills the clustershell task before quitting the last command prompt
        '''
        if cmdprompt is self.cmdstack[0]:
            self.logger.debug('Killing ClusterShell task')
            self.clustershell_task.abort(kill=True)

        super(Clustering, self).leave_mode(cmdprompt)

    # Dynamic keywords

    def get_nodesets(self, dyn_keyword=None):
        '''
        Returns the list of registered nodesets and description
        '''
        nodesets = self.nodesets.keys()
        nodesets.sort()

        nodesetmap = {}

        for nodeset in nodesets:
            nodesetmap[nodeset] = '%s nodeset' % nodeset

        return nodesetmap

    def display_symmetric_buffers(self, buffers):
        '''
        Displays the content of a shell task's buffers, and displays symmetric/asymmetric information
        '''
        for i in range(len(buffers)):
            if i is 0:
                if len(buffers) is 1:
                    print sysadmintoolkit.utils.get_green_text('Symmteric')
                else:
                    print sysadmintoolkit.utils.get_red_text('Asymmteric')

            print '      %s:' % ', '.join(buffers[i][1])
            print sysadmintoolkit.utils.indent_text(buffers[i][0], indent=8, width=self.cmdstack[-1].width)

    # Sysadmin-toolkit commands

    def display_symmetric_files(self, line, mode):
        '''
        Displays symmetric files for the specified group
        '''
        if 'group' in line:
            group = [line.split()[-1]]
        else:
            group = self.get_nodesets().keys()
            group.sort()

        self.logger.debug('Displaying symmetric files for groups: %s' % group)

        for nodeset in group:
            print 'Group: %s' % nodeset
            print

            sym_file_keys = self.symmetric_files[nodeset].keys()
            sym_file_keys.sort()

            for sym_file in sym_file_keys:
                if 'recursive' in self.symmetric_files[nodeset][sym_file]:
                    self.clustershell_task.shell('find %s -type f | xargs md5sum' % sym_file, nodes=self.nodesets[nodeset])
                else:
                    self.clustershell_task.shell('md5sum %s' % sym_file, nodes=self.nodesets[nodeset])

                if len(self.symmetric_files[nodeset][sym_file]):
                    print '  %s (%s):' % (sym_file, ','.join(self.symmetric_files[nodeset][sym_file])),
                else:
                    print '  %s:' % sym_file,

                self.clustershell_task.resume()

                self.display_symmetric_buffers([bufr_nodes for bufr_nodes in self.clustershell_task.iter_buffers()])

    def display_symmetric_commands(self, line, mode):
        '''
        Displays symmetric commands for the specified group
        '''
        if 'group' in line:
            group = [line.split()[-1]]
        else:
            group = self.get_nodesets().keys()
            group.sort()

        self.logger.debug('Displaying symmetric commands for groups: %s' % group)

        for nodeset in group:
            print 'Group: %s' % nodeset
            print

            for sym_command in self.symmetric_commands[nodeset]:
                self.clustershell_task.shell(sym_command, nodes=self.nodesets[nodeset])

                print '  "%s" :' % sym_command,

                self.clustershell_task.resume()

                self.display_symmetric_buffers([bufr_nodes for bufr_nodes in self.clustershell_task.iter_buffers()])

    def debug(self, line, mode):
        '''
        Displays clustering configuration and state
        '''
        for nodeset in self.nodesets:
            if nodeset not in self.reachable_nodes:
                self.test_reachability(nodeset)

        print 'Clustering plugin configuration and state:'
        print
        print '  Clustering plugin version: %s' % __version__
        print '  ClusterShell version: %s' % ClusterShell.__version__
        print

        registered_nodes = self.nodesets.keys()
        registered_nodes.remove('default')
        registered_nodes.sort()
        registered_nodes.insert(0, 'default')

        print '  *** Registered node groups ***'
        print

        for nodeset in registered_nodes:
            print '    %s: %s' % (nodeset, str(self.nodesets[nodeset]).replace(',', ', '))
            print '    reachable nodes: %s' % (str(self.reachable_nodes[nodeset]).replace(',', ', '))
            print

        if len(self.symmetric_files):
            groups = self.symmetric_files.keys()
            groups.sort()

            print '  *** Symmetric files configuration ***'
            print

            for group in groups:
                print '    Group: %s' % group

                files = self.symmetric_files[group].keys()
                files.sort()

                for file in files:
                    print '      %s' % file,

                    if len(self.symmetric_files[group][file]) > 0:
                        print '(%s)' % ','.join(self.symmetric_files[group][file])
                    else:
                        print

                print

        if len(self.symmetric_commands):
            groups = self.symmetric_commands.keys()
            groups.sort()

            print '  *** Symmetric commands configuration ***'
            print

            for group in groups:
                print '    Group: %s' % group

                for command in self.symmetric_commands[group]:
                    print '      %s' % command

                print
