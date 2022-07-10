#!/usr/bin/env bash
sudo supervisorctl stop tradebot
git pull
pdm install
sudo supervisorctl start tradebot
echo "ok"
