#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade
apt-get install -y python python-pip python-dev

cd /vagrant
sudo python setup.py develop
