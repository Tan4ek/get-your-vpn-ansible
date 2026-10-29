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
   - edit non-secret variables in `inventory/group_vars/all.yml`.
   - create `secrets.vault.yml` with `ansible-vault create secrets.vault.yml`. Set `openvpn_private_key` and `get_your_vpn_config_api_key` there. Use a unique random API key of at least 32 characters containing only letters, digits, `_` or `-` (for example, generate one locally with `openssl rand -hex 32`). There is no default API key: deployment rejects a missing or invalid value before running service roles, and the config role also checks it before rendering files. Keep the Vault password outside Git.
4. Login on target machine (where you will install `get-your-vpn`), [install docker](https://docs.docker.com/engine/install/), [install docker-compose](https://docs.docker.com/compose/install/). Or you can install docker & docker-compose via ansible
`ansible-playbook --private-key=~/.ssh/local-ubuntu-server -i=inventory --user=fuck-rkn --become -K install-docker.yml`

## Run installation

`ansible-playbook --private-key={{ path to ssh key for server }} -i=inventory --user={{ ssh user }} --become -K --ask-vault-pass -e @secrets.vault.yml deploy-application.yml`

## Management API access

OpenVPN and Outline management ports, Prometheus, and both metrics exporters bind to `127.0.0.1` on the Docker host. Public VPN traffic still uses UDP port `1194` and TCP port `443`. The applications communicate over the shared `get-your-vpn` Docker network using container ports `8090` (OpenVPN), `8080` (Outline), `9090` (Prometheus), `9176` (OpenVPN metrics) and `9091` (Outline metrics); changing a published host port does not change these internal addresses. Prometheus continues to scrape both exporters internally. Remote scripts or monitoring that called a provider or metrics API directly must use a protected local connection, such as an SSH tunnel.

Use Docker Engine 28 or later with the default bridge NAT behavior: [older Docker versions allow hosts on the same L2 network to reach localhost-published ports](https://docs.docker.com/engine/network/port-publishing/).

The `get-your-vpn-config` frontend API remains published on `get_your_vpn_config_container_port` (default `8091`). Configure its administrative clients with the matching `X-Api-Key` and use an authenticated TLS reverse proxy or another protected connection so the key is not sent over public plaintext HTTP. The generated `config.ini` belongs to root, has mode `0600`, and is mounted read-only. Ansible suppresses its content in output and diffs. Apply the deployment and update clients together when replacing the former shared example key.

## Local checks

In the Python environment where Ansible is installed, run `python -m unittest discover -s tests -v`. These checks render templates with synthetic values and execute only the API-key assertion in a local temporary playbook. They do not deploy services or connect to inventory hosts.

## After installation

1. Check docker containers `docker ps -f name=get-your-vpn`.
2. If openvpn not initialized (first run) follow [this manual](https://github.com/kylemanna/docker-openvpn/blob/master/docs/docker-compose.md). Use password for primary key from `openvpn_private_key` config.

## What needs to install manually  

[Install frontend](https://github.com/TimAle/get-your-vpn-config-ui) for invite link and vpn provider manager. 
