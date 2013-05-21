# Clustering Plugin #

A Sysadmin-Toolkit Plugin that can validate that commands and files are symmetric across a cluster of Linux machines.

## Plugin Description ##

The Clustering Plugin is built for Sysadmin Toolkit and provides basic cluster health checking, such as verifying that configured files and command are the same.

Built on the ClusterShell python package, it provides to other plugins a way to execute shell commands to nodes of a cluster.

## Installation ##

Clustering Plugin is coded for python 2.7 on Ubuntu 12.04, and requires the following packages:

- Sysadmin-Toolkit ([https://github.com/lpther/SysadminToolkit](https://github.com/lpther/SysadminToolkit))
- ClusterShell 1.6 ([https://github.com/cea-hpc/clustershell](https://github.com/cea-hpc/clustershell))

## Basic Usage ##

Either use ClusterShell's group configuration to define all your groups to host mapping, or list nodes in the default-nodeset configuration option.

    echo "all: node-[1-2]" > /etc/clustershell/groups

Define in the configuration file the default nodeset, symmetric files and commands:

    [clustering]
    default-nodeset = @all
    
    symmetric-files = /etc/resolv.conf,
      /etc/r*.conf,
      recursive|/etc/udev/rules.d,
      /etc/hostname,
    
    symmetric-commands = @all:uname | grep -i Linux,
     @all:echo $RANDOM \; uptime,

Display files that are supposed to be exactly the same across the cluster:

	sysadmin-toolkit# show cluster symmetric-files
	Group: default

	  /etc/resolv.conf: Symmteric
	      node-1, node-2:
	        8aa7cfabf13c9f9ae48176fcba4a17bc  /etc/resolv.conf
	
	  /etc/hostname: Asymmetric
	      node-2:
	        6d8d0a4b57ecac70623624eb45489571  /etc/hostname
	
	      node-1:
	        43b43e627630d21ef803d47c4a4b8976  /etc/hostname
	
	  /etc/r*.conf: Symmteric
	      node-1, node-2:
	        6a05320976aec88f9aa3ca964e2032f7  /etc/rsyslog.conf
	        8aa7cfabf13c9f9ae48176fcba4a17bc  /etc/resolv.conf
	
	  /etc/udev/rules.d (recursive): Asymmetric
	      node-1:
	        3b6de9f3f911176734c66903b4f8735c  /etc/udev/rules.d/README
	        40f92b969ccc80deddc428d3ea2e9739  /etc/udev/rules.d/70-persistent-cd.rules
	        572f30a27275db3351fd40fa25afc0fb  /etc/udev/rules.d/70-persistent-net.rules
	
	      node-2:
	        3b6de9f3f911176734c66903b4f8735c  /etc/udev/rules.d/README
	        40f92b969ccc80deddc428d3ea2e9739  /etc/udev/rules.d/70-persistent-cd.rules
	        d1175f6d8a17b5e8c82c52b547e33676  /etc/udev/rules.d/70-persistent-net.rules

Display commands that should return the same output across the cluster:

    sysadmin-toolkit# show cluster symmetric-commands
    Group: @all
    
      "echo $RANDOM ; uptime" : Asymmetric
          node-2:
            18910
             02:13:00 up 24 days,  7:15,  2 users,  load average: 0.00, 0.01, 0.05
    
          node-1:
            20614
             02:13:00 up 24 days,  7:19,  8 users,  load average: 0.36, 0.14, 0.09
    
      "uname | grep -i Linux" : Symmteric
          node-2, node-1:
            Linux

Validate node reachability detected by the Plugin, and display configuration:

    sysadmin-toolkit# debug clustering
    Clustering plugin configuration and state:
    
      Clustering plugin version: 0.1.0a
      ClusterShell version: 1.6
    
      *** Registered node groups ***
    
        default: node-[1-2]
        reachable nodes: node-[1-2]
    
        @all: node-[1-2]
        reachable nodes: node-[1-2]
    
      *** Symmetric files configuration ***
    
        Group: @all
          /etc/resolv.conf
          /etc/hostname
          /etc/r*.conf
          /etc/udev/rules.d (recursive)
    
      *** Symmetric commands configuration ***
    
        Group: @all
          echo $RANDOM ; uptime
          uname | grep -i Linux

# Related Projects #

- Sysadmin-Toolkit ([https://github.com/lpther/SysadminToolkit](https://github.com/lpther/SysadminToolkit))