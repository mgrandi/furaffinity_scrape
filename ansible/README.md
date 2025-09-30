# README

the ansible playbook for installing the scrape submissions daemon


## requirements

a few modules from ansible:


### ansible-keepass
uses https://github.com/viczem/ansible-keepass for storage of various secrets

install on your local machine you are running ansible with:

```plaintext
pip install 'pykeepass==4.0.3' --user
ansible-galaxy collection install viczem.keepass
```

### pipx

uses the pipx module: https://docs.ansible.com/ansible/latest/collections/community/general/pipx_module.html

install on the local machine you are running ansible with:

```plaintext
ansible-galaxy collection install community.general
```

### environment variables

you need to set these environment variables

`FURAFFINITY_SCRAPE_ANSIBLE_KEEPASS_FILE_PATH` - the filepath to the keepass database
`ANSIBLE_KEEPASS_PSW  ` - the ansible keepass password
`FURAFFINITY_SCRAPE_CONFIG_FILE_PATH` - the path to the furaffinity scrape configuration file

if using the just file, there are a few more

`PERSONAL_KEEPASS_VAULT_FILE_PATH` - the other kepass vault that contains the password to the main ansible keepass vault (`FURAFFINITY_SCRAPE_ANSIBLE_KEEPASS_FILE_PATH`)
`PERSONAL_KEEPASS_VAULT_ENTRY` - the entry we want `keepassxc-cli` to fetch for the password for the main keepass vault