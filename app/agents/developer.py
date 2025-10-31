import logging
from typing import Optional, Dict, Any
import re
import autogen  # type: ignore
from autogen import AssistantAgent
from app.config import Config
from app.state import StateManager

DEVELOPER_SYSTEM_MESSAGE = """
Você é o Desenvolvedor (Developer).
Sua tarefa é escrever o código Python mínimo necessário para fazer os testes passarem.
Siga estritamente o ciclo TDD: RED (falha) → GREEN (passa) → REFACTOR (melhora).

Regras importantes:
1. Implemente APENAS o necessário para os testes passarem
2. Não adicione funcionalidades extras não testadas
3. Mantenha o código simples e legível
4. Siga as convenções PEP8
5. Use nomes descritivos para funções e variáveis
6. Adicione docstrings explicativos

Se os testes falharem:
- Analise o feedback de erro com atenção
- Identifique a causa raiz da falha
- Faça a correção mínima necessária

Você deve responder *apenas* com um único bloco de código Python que salva o arquivo.
Não adicione nenhum texto antes ou depois do bloco de código.

Exemplo de Resposta (para teste de soma):
```python
import os
os.makedirs('workspace', exist_ok=True)
with open('workspace/app_code.py', 'w') as f:
    f.write(\"""
def add(a: int, b: int) -> int:
    \"\"\"
    Soma dois números inteiros.
    
    Args:
        a: Primeiro número
        b: Segundo número
    
    Returns:
        int: Soma de a e b
    \"\"\"
    return a + b
\""")
print("✅ Código implementado em: workspace/app_code.py")
```
"""

def validate_implementation(code: str) -> Optional[str]:
    """
    Validar código implementado.
    
    Returns:
        str: Mensagem de erro se inválido, None se válido
    """
    if not code:
        return "Código vazio gerado"
    
    # Verificar se contém testes
    if "def test_" in code or "import pytest" in code:
        return "Código contém testes (deve estar em arquivo separado)"
    
    # Verificar se há pelo menos uma função
    if "def " not in code:
        return "Nenhuma função implementada"
    
    # Verificar docstrings
    func_pattern = r"def\s+(\w+)\s*\("
    funcs = re.finditer(func_pattern, code)
    for match in funcs:
        func_name = match.group(1)
        func_pos = match.start()
        next_lines = code[func_pos:func_pos + 200]  # Próximas linhas após função
        if '"""' not in next_lines and "'''" not in next_lines:
            return f"Função {func_name} não tem docstring"
    
    return None

def generate_code(state: StateManager) -> None:
    """
    Gerar/atualizar implementação baseada nos testes e feedback.
    
    Args:
        state: Gerenciador de estado do TDD
    """
    iteration = state.get("iteration", 1)
    logging.info("=" * 60)
    if iteration == 1:
        logging.info("💻 FASE 3 (TDD - GREEN): Gerando implementação inicial")
    else:
        logging.info(f"💻 FASE 5 (TDD - REFACTOR): Refatorando código (iteração {iteration})")
    logging.info("=" * 60)
    
    tests = state.get("tests", "")
    feedback = state.get("feedback", "")
    prev_code = state.get("code", "")
    
    # Criar agente e gerar código
    agent = get_agent()
    context = f"""
    TESTES ATUAIS:
    {tests}
    
    FEEDBACK (se houver):
    {feedback}
    
    CÓDIGO ANTERIOR (se houver):
    {prev_code}
    """
    
    # Criar um UserProxyAgent para receber a resposta
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        code_execution_config={"use_docker": False}
    )
    
    # Iniciar chat com o agente
    logging.info("💬 Iniciando conversa com Developer...")
    
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
            msg_type = "�"  # Código Python
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
            logging.debug(f"📊 Métricas: {chars} caracteres, {lines} linhas")
    
    # Iniciar chat com callback de logging
    response = user_proxy.initiate_chat(
        agent,
        message=f"Implemente código para passar nos testes:\n{context}",
        callback=log_chat_step
    )
    logging.info("💬 Conversa com Developer finalizada")
    
    # Extrair o código da última mensagem do assistente
    assistant_messages = [msg for msg in response.chat_history if msg["role"] == "assistant"]
    code = assistant_messages[-1]["content"] if assistant_messages else ""
    
    # Validar implementação
    if error := validate_implementation(code):
        logging.error(f"❌ {error}")
        if prev_code:
            logging.info("♻️ Mantendo implementação anterior...")
            code = prev_code
        else:
            raise ValueError(f"Falha ao gerar código válido: {error}")
    
    # Salvar implementação
    state.save_implementation_file(code)
    
    # Atualizar estado
    state.update(
        code=code,
        test_phase="green"
    )
    
    # Preview do código
    preview = code.split('\n')[:10]
    logging.info("📄 Preview da implementação:")
    for line in preview:
        logging.info(line)
    logging.info("...")

def get_agent() -> AssistantAgent:
    """Retorna uma instância do Agente Desenvolvedor"""
    return AssistantAgent(
        name="Developer",
        system_message=DEVELOPER_SYSTEM_MESSAGE,
        llm_config=Config.get_llm_config(),
    )
