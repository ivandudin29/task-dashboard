#!/bin/bash
# Очищаем кэш pip и виртуальное окружение перед установкой
rm -rf .venv
pip cache purge || true
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
