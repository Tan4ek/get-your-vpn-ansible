# get-your-vpn-ansible

# Preparation
Установить зависимости

`ansible-galaxy install -r requirements.yml`

Установить docker

`ansible-playbook --private-key=~/.ssh/local-ubuntu-server -i=inventory --user=fuck-rkn --become -K install-docker.yml`

Установить get-your-vpn

`ansible-playbook --private-key=~/.ssh/local-ubuntu-server -i=inventory --user=fuck-rkn --become -K deploy-application.yml`