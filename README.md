# Platform 9 Deployment Unit Services

These are services that are instantiated in a per-customer account unit.

They currently include:

* Backbone (host management)
* Resource Manager
* du-tools

# FAQ

- Where are roles defined? 

 `cat /etc/pf9/resmgr_roles/pf9-kube/3.8.0-5673/pf9-kube-role.json`

Each github repo has potentially one or more RPMs/roles that it may have associated with it.

- What are the contents of a role? 

Roles have a URL to a RPM, and other config information, for example, versions.

Example config for a role json.
 ``` file: ceilometr 
 config:{
    pf9-ceilometer: { <--  app
        url: ceilometer-1.0.rpm  <--- pkg
     }
     pf9-bannas: { <--  another app 
        url: bannana.rpm <-- pkg 
     }
 }
 ```

As an example 
`python /opt/pf9/pf9-support/config --get-services`

*To change it at runteime*

You can edit the files: 
` vi /opt/pf9/resmgr/lib/python2.7/site-packages/resmgr/` 

And then `systemctl stop pf9-resmgr`

### How do resource manager RPMs reach a host?

The DU has wrapper RPMs to each RPM that might run on the host.
The wrappper RPM has a RPM inside of it, which causes the 
RPM which runs on the DU, to be exposed when it the wrapper is installed.

The HOST can then pull this RPM down.

On the DU theres a kube wrapper: 

```
[jay@jayunit100 ~]$ rpm -ql pf9-kube-wrapper-3.8.0-5673.e39477a.x86_64
/etc/pf9/resmgr_roles
/etc/pf9/resmgr_roles/conf.d
/etc/pf9/resmgr_roles/conf.d/pf9-kube-role.conf
/etc/pf9/resmgr_roles/pf9-kube
/etc/pf9/resmgr_roles/pf9-kube/3.8.0-5673
/etc/pf9/resmgr_roles/pf9-kube/3.8.0-5673/pf9-kube-role.json
/opt/pf9
/opt/pf9/www
/opt/pf9/www/private
/opt/pf9/www/private/pf9-kube-3.8.0-5673.x86_64.deb
/opt/pf9/www/private/pf9-kube-3.8.0-5673.x86_64.rpm
```

Meanwhile, once installed,  the RPM that is pulled down
from the DU, can be seen in a *host* node, like this:

```                                           
[root@jay-pfk-machine-2 pf9-kube]# rpm -ql pf9-kube-3.8.0-5673.x86_64      
/etc/cni/net.d                                                          
/etc/logrotate.d/pf9-kube                                        
/etc/pf9/comms/sni_maps/docker.json                                         
/etc/pf9/comms/sni_maps/kubernetes-keystone.json                            
/etc/pf9/kube.d                                                
/etc/rc.d/init.d/pf9-kube                                 
/etc/sudoers.d/pf9-kube                                              
/opt/cni/bin                                                      
/opt/cni/bin/bridge                                               
/opt/cni/bin/cnitool                                              
/opt/cni/bin/dhcp                                               
/opt/cni/bin/flannel               
```

