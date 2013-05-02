==========
clustering
==========

[clustering]
# Plugin to provide communication to a set of nodes
# Python package "clustershell" must be installed

# Default group for cluster commands
# Either a list of nodes, or some configured
# in clustershell (/etc/clustershell/groups)
default-nodeset = @group

# Comma separated list of files to verify
# if they are symmetric for the provided group (md5sum based)
# syntax:
# Single file or a directory with the same pattern match as linux's ls
#  @group:/path/to/some/file
#  @group:/path/to/some/dir/*
# To verify a directory recursively
#  @group:recursive:/path/to/some/dir
symmetric-files = @all:/etc/resolv.conf

## show cluster nodes -> Displays all available nodes in the default-nodeset and their reachability
## show cluster groups -> Displays available groups
## show cluster group <group> -> Display the node group and their reachability 
## show cluster symmtric-files -> Verify symmetric files across the cluster
