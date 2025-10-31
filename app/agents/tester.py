import logging
from typing import Optional, Dict, Any
import autogen  # type: ignore
from autogen import AssistantAgent
from app.config import Config
from app.state import StateManager

TESTER_SYSTEM_MESSAGE = """
Você é o Engenheiro de Testes TDD (Tester).
Sua responsabilidade é escrever os casos de teste `pytest` com base no plano fornecido.
Você deve escrever os testes *antes* que qualquer código de aplicação exista (princípio TDD).

Regras importantes:
1. O código da aplicação estará em `app_code.py`
2. Use imports relativos: `from app_code import ...`
3. Escreva testes completos que cubram diferentes cenários
4. Use nomes descritivos para os testes (ex: test_add_positive_numbers)
5. Inclua docstrings explicando o propósito de cada teste
6. Evite implementar a funcionalidade nos testes

Você deve responder *apenas* com um único bloco de código Python que cria o arquivo de teste.
Não adicione nenhum texto antes ou depois do bloco de código.

Exemplo de Resposta:
```python
import os
os.makedirs('workspace', exist_ok=True)
with open('workspace/test_app.py', 'w') as f:
    f.write(\"""
import pytest
from app_code import add

def test_add_positive_numbers():
    \"\"\"Testar soma de números positivos\"\"\"
    assert add(2, 3) == 5

def test_add_negative_numbers():
    \"\"\"Testar soma com números negativos\"\"\"
    assert add(-2, -3) == -5

def test_add_zero():
    \"\"\"Testar soma com zero (elemento neutro)\"\"\"
    assert add(5, 0) == 5
    assert add(0, 5) == 5
\""")
print("✅ Testes criados em: workspace/test_app.py")
```
"""

def validate_tests(tests: str) -> Optional[str]:
    """
    Validar conteúdo dos testes gerados.
    
    Returns:
        str: Mensagem de erro se inválido, None se válido
    """
    if not tests:
        return "Testes vazios gerados"
    
    if "def test_" not in tests:
        return "Nenhuma função de teste encontrada"
        
    module_name = Config.IMPLEMENTATION_MODULE
    if (f"from {module_name} import" not in tests and 
        f"import {module_name}" not in tests):
        return f"Testes não importam de '{module_name}'"
    
    # Verificar se há implementação nos testes
    non_test_funcs = []
    for line in tests.split('\n'):
        stripped = line.strip()
        if (stripped.startswith('def ') and 
            'def test_' not in stripped and 
            '@pytest.fixture' not in tests[max(0, tests.find(line)-100):tests.find(line)]):
            non_test_funcs.append(stripped)
    
    if non_test_funcs:
        return f"Testes contêm implementação: {non_test_funcs}"
    
    return None

def generate_tests(specification: str, state: StateManager) -> None:
    """
    Gerar testes baseados na especificação.
    
    Args:
        specification: Especificação do que deve ser testado
        state: Gerenciador de estado do TDD
    """
    iteration = state.get("iteration", 1)
    logging.info("=" * 60)
    if iteration == 1:
        logging.info("📝 FASE 1 (TDD): Gerando testes iniciais")
    else:
        logging.info(f"📝 REGENERANDO TESTES (iteração {iteration})")
    logging.info("=" * 60)
    
    # Guardar testes anteriores antes de gerar novos
    previous_tests = state.get("tests", "")
    if previous_tests:
        logging.info("📦 Backup: Salvando testes anteriores...")
        logging.debug(f"Testes anteriores ({len(previous_tests)} chars)")
    
    # Criar agentes para o processo
    logging.info("🔧 Configurando agentes para geração de testes...")
    agent = get_agent()
    
    # Criar um UserProxyAgent para receber a resposta
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        code_execution_config={"use_docker": False}
    )
    logging.debug("✓ Agentes configurados")
    
    # Configurar logging detalhado da conversa
    def log_chat_step(message: Dict[str, Any]) -> None:
        """Log detalhado de cada etapa da conversa"""
        content = message.get("content", "")
        role = message.get("role", "unknown")
        name = message.get("name", "unknown")
        
        # Determinar direção e ícone da mensagem
        if role == "user":
            icon, direction = "👤", "→"
            source, target = name, agent.name
        else:
            icon, direction = "🤖", "←"
            source, target = agent.name, "user"
            
        # Detectar tipo de mensagem
        msg_type = "📝"  # Texto normal
        if not content.strip():
            msg_type = "⚪"  # Mensagem vazia
            logging.debug(f"{msg_type} Mensagem vazia detectada de {source}")
        elif "```python" in content:
            msg_type = "💻"  # Código Python
            logging.debug(f"{msg_type} Bloco de código Python detectado")
        elif content.startswith(">>>>>>>> EXECUTING"):
            msg_type = "⚡"  # Execução
            logging.debug(f"{msg_type} Execução de código iniciada")
        elif "exitcode:" in content:
            msg_type = "🔄"  # Resultado de execução
            logging.debug(f"{msg_type} Resultado de execução recebido")
        
        # Formatar e truncar mensagem para log
        msg_preview = content.replace("\n", "\\n")[:100] if content.strip() else "(vazia)"
        if len(content) > 100:
            msg_preview += "..."
            
        # Log da interação com tipo de mensagem
        logging.info(f"{msg_type} {icon} {source} {direction} {target}: {msg_preview}")
        
        # Log de métricas
        if content.strip():
            chars = len(content)
            lines = len(content.split("\n"))
            logging.debug(f"� Métricas: {chars} caracteres, {lines} linhas")
    
    # Iniciar processo de geração
    logging.info("\n" + "=" * 40)
    logging.info("💬 INICIANDO GERAÇÃO DE TESTES")
    logging.info("=" * 40)
    
    # Iniciar chat com callback de logging
    response = user_proxy.initiate_chat(
        agent,
        message=f"Gere testes pytest para: {specification}",
        callback=log_chat_step
    )
    
    logging.info("💬 Conversa com Tester finalizada")
    
    # Extrair e processar resposta
    logging.info("🔍 Processando resposta do Tester...")
    assistant_messages = [msg for msg in response.chat_history if msg["role"] == "assistant"]
    
    if not assistant_messages:
        logging.error("❌ Nenhuma resposta válida do Tester!")
        raise ValueError("Tester não gerou resposta")
        
    tests = assistant_messages[-1]["content"]
    logging.info(f"✓ Resposta extraída ({len(tests)} chars)")
    
    # Validar testes gerados
    logging.info("🔍 Validando testes gerados...")
    if error := validate_tests(tests):
        logging.error(f"❌ Validação falhou: {error}")
        if previous_tests:
            logging.warning("⚠️ Restaurando testes anteriores devido a erro...")
            tests = previous_tests
            logging.info("✓ Testes anteriores restaurados")
        else:
            logging.error("❌ Sem testes anteriores para restaurar")
            raise ValueError(f"Falha ao gerar testes válidos: {error}")
    else:
        logging.info("✓ Validação de testes OK")
    
    # Salvar testes
    logging.info("💾 Salvando testes em arquivo...")
    state.save_test_file(tests)
    
    # Atualizar estado
    logging.info("📊 Atualizando estado do TDD...")
    state.update(
        tests=tests,
        test_phase="red",
        previous_tests=previous_tests
    )
    
    # Preview dos testes
    logging.info("\n" + "=" * 40)
    logging.info("📄 PREVIEW DOS TESTES GERADOS")
    logging.info("=" * 40)
    preview = tests.split('\n')[:10]
    for line in preview:
        logging.info(line)
    if len(tests.split('\n')) > 10:
        logging.info("...")
    logging.info("=" * 40)

def get_agent() -> AssistantAgent:
    """Retorna uma instância do Agente de Testes"""
    return AssistantAgent(
        name="Tester",
        system_message=TESTER_SYSTEM_MESSAGE,
        llm_config=Config.get_llm_config(),
    )
