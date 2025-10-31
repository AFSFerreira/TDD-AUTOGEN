"""
Script principal para executar o TDD Autogen.
Este script deve ser executado da raiz do projeto.
"""
import os
import sys

# Adicionar diretório raiz ao PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.main import main

if __name__ == "__main__":
    main()
