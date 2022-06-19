# get-your-vpn-ansible

## What is it?

Ansible playbook to install `get-your-vpn` on system via ssh.

On target machine will be installed:
- [get-your-vpn-config](https://github.com/Tan4ek/get-your-vpn-config) - invite link and vpn provider manager
- [outline-ss proxy with management api](https://github.com/Tan4ek/outline-ss-server-user-manager) - shadowsocks proxy provider
- [openvpn with management api](https://github.com/Tan4ek/openvpn-http-api) - openvpn server
- [prometheus server](https://prometheus.io/) - metrics for vpn providers
- [openvpn prometheus exporter](https://github.com/kumina/openvpn_exporter) - expose openvpn metrics

All application are installed using docker and docker-compose.

## Preparation

1. [Install ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) on local machine
2. Install ansible dependencies on local machine
`ansible-galaxy install -r requirements.yml`
3. Prepare ansible-inventory, variables and secrets. 
   - `cp -r inventory-example inventory`
   - set host where will be installed `get-your-vpn` to `inventory/hosts` file.
   - edit `inventory/group_vars/all.yml`, change variables (specially `openvpn_private_key`)  
4. Login on target machine (where you will install `get-your-vpn`), [install docker](https://docs.docker.com/engine/install/), [install docker-compose](https://docs.docker.com/compose/install/). Or you can install docker & docker-compose via ansible
`ansible-playbook --private-key=~/.ssh/local-ubuntu-server -i=inventory --user=fuck-rkn --become -K install-docker.yml`

## Run installation

`ansible-playbook --private-key={{ path to ssh key for server }} -i=inventory --user={{ ssh user }} --become -K deploy-application.yml`