import ClusterShell
import ClusterShell.Task
import sysadmintoolkit
import logging

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

        self.logger.debug('Clustering plugin started with default nodes: %s' % self.nodesets['default'])

    def start_task(self):
        self.clustershell_task = ClusterShell.Task.task_self()
        self.clustershell_task.set_info('connect_timeout', self.task_connect_timeout)
        self.clustershell_task.set_info('fanout', 512)

        if self.logger.getEffectiveLevel() is logging.DEBUG:

            def log_debug(task, msg):
                self.logger.debug('Clustershell task %s: %s' % (task, msg))

            self.clustershell_task.set_info('debug', True)
            self.clustershell_task.set_info('print_debug', log_debug)

    def register_symmetric_files(self):
        for entry in self.config['symmetric-files'].split(','):
            if entry is '':
                continue

            if ':' in entry:
                group = entry.strip().split(':')[0]
                file = ':'.join(entry.strip().split(':')[1:])
            else:
                group = 'default'
                file = entry.strip()

            if group is '' or '/' in group or not group.startswith('@'):
                group = 'default'
            else:
                group_nodeset = ClusterShell.NodeSet.NodeSet(group)

                if group not in self.nodesets:
                    if not self.register_nodes(group, group):
                        continue

            if group not in self.symmetric_files:
                self.symmetric_files[group] = []

            self.logger.debug('Adding symmetric file "%s" to group %s' % (file, group))

            self.symmetric_files[group].append(file)
            self.symmetric_files[group].sort()

    def register_symmetric_commands(self):
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
        worker = self.clustershell_task.shell('echo CONNECTED', nodes=self.nodesets[nodeset])
        self.clustershell_task.resume()

        reachable_nodes = []

        for buf , nodes in self.clustershell_task.iter_buffers() :
            if 'CONNECTED' in buf:
                for reachable_node in nodes:
                    reachable_nodes.append(reachable_node)

        self.reachable_nodes[nodeset] = ClusterShell.NodeSet.NodeSet(','.join(reachable_nodes))

    def leave_mode(self, cmdprompt):
        '''
        '''
        if cmdprompt is self.cmdstack[0]:
            self.logger.debug('Killing ClusterShell task')
            self.clustershell_task.abort(kill=True)

        super(Clustering, self).leave_mode(cmdprompt)

    def debug(self, line, mode):
        '''
        Displays clustering configuration and state
        '''
        for nodeset in self.nodesets:
            if nodeset not in self.reachable_nodes:
                self.test_reachability(nodeset)

        print 'Clustering plugin configuration and state:'
        print
        print '  ClusterShell Version: %s' % ClusterShell.__version__
        print

        registered_nodes = self.nodesets.keys()
        registered_nodes.remove('default')
        registered_nodes.sort()
        registered_nodes.insert(0, 'default')

        for nodeset in registered_nodes:
            print '  Node group %s: %s - Reachable Nodes: %s' % (nodeset, str(self.nodesets[nodeset]).replace(',', ', '), str(self.reachable_nodes[nodeset]).replace(',', ', '))

        print

        if len(self.symmetric_files):
            groups = self.symmetric_files.keys()
            groups.sort()

            print '  Symmetric files configuration:'
            print

            for group in groups:
                print '    Group: %s' % group

                for file in self.symmetric_files[group]:
                    print '      %s' % file

                print

            print

        if len(self.symmetric_commands):
            groups = self.symmetric_commands.keys()
            groups.sort()

            print '  Symmetric commands configuration:'
            print

            for group in groups:
                print '    Group: %s' % group

                for command in self.symmetric_commands[group]:
                    print '      %s' % command

                print

            print

