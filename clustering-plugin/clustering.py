__version__ = '0.1.0b'
__website__ = 'https://github.com/lpther/Clustering'

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
    '''
    Description
    -----------

    Provides cluster synchronization verification and clustering services to other plugins.

    Requirements
    ------------

    The clustering plugin requires the ClusterShell package, version
    *1.6* or more.

    Configuration
    -------------

    *default-nodeset*
      This is the nodeset used by default if no nodeset is specified.

      Groups configured in /etc/clustershell/groups can be used for the
      default nodeset.

      Default: @all

    *symmetric-files*
      Verify that these files are symmetric across the cluster using md5sum.

      Syntax:

      recursive: Verify recursively in a directory.

      @group: Group defined in the clustershell configuration



      ::

        symmetric-files = [@group:][recursive|]<filename1> ,
                          [@group:][recursive|]<filename2> ,
                          ...
                          [@group:][recursive|]<filenameN>

      Examples:

      ::

        symmetric-files = /etc/resolv.conf,
                          @all:/etc/r*.conf,
                          recursive|/etc/udev/rules.d,
                          @mygroup:/etc/hostname,

      Note: Wildcards can be used, as they are passed to a shell to launch md5sum.

      Default: None

    *symmetric-commands*
      Verify that output from these commands are symmetric across.

      Examples:

      ::

        symmetric-commands = @all:uname | grep -i Linux,
                             @all:echo $RANDOM \; uptime,

      Default: None

    '''

    def __init__(self, logger, config):
        super(Clustering, self).__init__('clustering', logger, config, version=__version__)

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
            self.logger.warning('Node entry %s could not be resolved. Is it defined in the clustershell groups file?' % setname)
            return False
        else:
            self.nodesets[setname] = newnodeset
            return True

    def get_nodeset(self, setname):
        if setname in self.nodesets:
            return self.nodesets[setname]
        else:
            self.logger.error('Nodeset %s is not registered' % setname)
            raise sysadmintoolkit.exception.PluginError('Nodeset %s is not registered' % setname, errno=300, plugin=self)

    def get_reachable_nodes(self, setname):
        if setname in self.reachable_nodes:
            return self.reachable_nodes[setname]
        else:
            if setname in self.nodesets:
                self.test_reachability(setname)
                return self.reachable_nodes[setname]
            else:
                self.logger.error('Nodeset %s is not registered' % setname)
                raise sysadmintoolkit.exception.PluginError('Nodeset %s is not registered' % setname, errno=300, plugin=self)

    def test_reachability(self, nodeset='default'):
        '''
        Simple test to ensure nodes are reachable
        '''
        self.logger.debug('Testing reachability for nodeset %s' % nodeset)

        buffer_nodes_list = self.run_cluster_command('echo CONNECTED', self.nodesets[nodeset])

        reachable_nodes = []

        for buf, nodes in buffer_nodes_list :
            if 'CONNECTED' in buf:
                for reachable_node in nodes:
                    reachable_nodes.append(reachable_node)

        self.reachable_nodes[nodeset] = ClusterShell.NodeSet.NodeSet(','.join(reachable_nodes))

    def get_reachable_nodes(self, nodesetname):
        if nodesetname not in self.reachable_nodes:
            if nodesetname not in self.nodesets:
                self.logger.error('Trying to get reachable nodes for a non registered nodeset (%s)' % nodesetname)
                return ClusterShell.NodeSet.NodeSet()
            else:
                self.test_reachability(nodesetname)

        return self.reachable_nodes[nodesetname]

    def leave_mode(self, cmdprompt):
        '''
        Kills the clustershell task before quitting the last command prompt
        '''
        if cmdprompt is self.cmdstack[0]:
            self.logger.debug('Killing ClusterShell task')
            self.clustershell_task.abort(kill=True)

        super(Clustering, self).leave_mode(cmdprompt)

    def display_symmetric_buffers(self, buffers):
        '''
        Displays the content of a shell task's buffers, and displays symmetric/asymmetric information
        '''
        for i in range(len(buffers)):
            if i is 0:
                if len(buffers) is 1:
                    print sysadmintoolkit.utils.get_green_text('Symmteric')
                else:
                    print sysadmintoolkit.utils.get_red_text('Asymmetric')

            print '      %s:' % ', '.join(buffers[i][1])
            print sysadmintoolkit.utils.indent_text(buffers[i][0], indent=8, width=self.cmdstack[-1].width)

    def run_cluster_command(self, command, nodeset):
        '''
        Returns a list of (buffer,nodes) of the executed command on nodes
        from the nodesetname.
        '''
        self.logger.debug('Running command "%s" on nodeset %s' % (command, nodeset))

        self.clustershell_task.shell(command, nodes=nodeset)
        self.clustershell_task.resume()

        return [(buffer, nodes) for (buffer, nodes) in self.clustershell_task.iter_buffers()]

    # Dynamic keywords

    def get_nodesets(self, user_input_obj=None):
        '''
        Returns the list of registered nodesets and description
        '''
        nodesets = self.nodesets.keys()
        nodesets.sort()

        nodesetmap = {}

        for nodeset in nodesets:
            nodesetmap[nodeset] = '%s nodeset' % nodeset

        return nodesetmap

    # Sysadmin-toolkit commands

    def display_symmetric_files(self, user_input_obj):
        '''
        Displays symmetric files for the specified group
        '''
        line = user_input_obj.get_entered_command()

        if 'group' in line:
            group = [line.split()[line.split().index('group') + 1]]
        else:
            group = self.get_nodesets().keys()
            group.sort()

        self.logger.debug('Displaying symmetric files for groups: %s' % group)

        for nodeset in group:
            if nodeset not in self.symmetric_files:
                continue

            print 'Group: %s' % nodeset
            print

            sym_file_keys = self.symmetric_files[nodeset].keys()
            sym_file_keys.sort()

            for sym_file in sym_file_keys:
                if 'recursive' in self.symmetric_files[nodeset][sym_file]:
                    buffer_nodes_list = self.run_cluster_command('find %s -type f | xargs md5sum | sort' % sym_file, self.get_reachable_nodes(nodeset))
                else:
                    buffer_nodes_list = self.run_cluster_command('md5sum %s | sort' % sym_file, self.get_reachable_nodes(nodeset))

                if len(self.symmetric_files[nodeset][sym_file]):
                    print '  %s (%s):' % (sym_file, ','.join(self.symmetric_files[nodeset][sym_file])),
                else:
                    print '  %s:' % sym_file,

                self.display_symmetric_buffers(buffer_nodes_list)

    def display_symmetric_commands(self, user_input_obj):
        '''
        Displays symmetric commands for the specified group
        '''
        line = user_input_obj.get_entered_command()

        if 'group' in line:
            group = [line.split()[line.split().index('group') + 1]]
        else:
            group = self.get_nodesets().keys()
            group.sort()

        self.logger.debug('Displaying symmetric commands for groups: %s' % group)

        for nodeset in group:
            if nodeset not in self.symmetric_commands:
                continue

            print 'Group: %s' % nodeset
            print

            for sym_command in self.symmetric_commands[nodeset]:
                buffer_nodes_list = self.run_cluster_command(sym_command, self.get_reachable_nodes(nodeset))

                print '  "%s" :' % sym_command,

                self.display_symmetric_buffers(buffer_nodes_list)

    def debug(self, user_input_obj):
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
