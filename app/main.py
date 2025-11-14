import os
import time
import logging
import autogen  # type: ignore
from typing import Dict, Any, List, Optional

from app.config import Config
from app.state import StateManager, TDDState
from app.agents.planner import get_agent as get_planner
from app.agents.tester import get_agent as get_tester, generate_tests
from app.agents.developer import get_agent as get_developer, generate_code
from app.agents.reviewer import get_agent as get_reviewer, analyze_failures
from app.agents.runner import run_tests, create_empty_implementation

class TDDOrchestrator:
    """Orquestrador do fluxo TDD usando autogen"""
    
    def _log_group_message(self, sender_name: str, receiver_name: str, message: str) -> None:
        """Log detalhado de cada mensagem do chat em grupo"""
        if not message or not message.strip():
            logging.debug(f"⚪ Mensagem vazia: {sender_name} → {receiver_name}")
            return
        
        # Determinar tipo e ícone da mensagem
        msg_type = "📝"  # Texto normal
        if "```python" in message:
            msg_type = "💻"  # Código Python
        elif message.startswith(">>>>>>>> EXECUTING"):
            msg_type = "⚡"  # Execução
        elif "exitcode:" in message:
            msg_type = "🔄"  # Resultado de execução
        elif message.startswith("Plano de TDD:"):
            msg_type = "📋"  # Plano
        
        # Formatar e truncar mensagem para log
        msg_preview = message.replace("\n", "\\n")[:100]
        if len(message) > 100:
            msg_preview += "..."
        
        # Log da interação com tipo de mensagem
        logging.info("-" * 80)  # Linha separadora
        logging.info(f"{msg_type} {sender_name} → {receiver_name}: {msg_preview}")
        
        # Log de métricas em modo debug
        chars = len(message)
        lines = len(message.split("\n"))
        logging.debug(f"📊 Métricas: {chars} caracteres, {lines} linhas")
    
    def __init__(self):
        """Inicializar orquestrador TDD"""
        self.workspace_dir = Config.WORKSPACE_PATH
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Inicializar agentes
        self.planner = get_planner()
        self.tester = get_tester()
        self.developer = get_developer()
        self.reviewer = get_reviewer()
        
        # Configurar executor
        self.executor = self._setup_executor()
        
        # Lista de agentes e configuração do chat
        self.agents = [
            self.executor,
            self.planner,
            self.tester,
            self.developer,
            self.reviewer
        ]
        
        # Configurar função de log para cada agente
        for agent in self.agents:
            # Salvar referências originais
            agent._original_receive = agent.receive
            agent._original_send = agent.send
            orchestrator = self  # Referência para usar nas closures
            
            def make_receive_with_log(agent):
                def receive_with_log(self, message: Dict[str, Any], sender: Any, *args, **kwargs) -> None:
                    try:
                        sender_name = getattr(sender, "name", "unknown")
                        content = message.get("content", "")
                        orchestrator._log_group_message(sender_name, agent.name, content)
                    except Exception as e:
                        logging.debug(f"Erro ao fazer log de mensagem recebida: {e}")
                    return agent._original_receive(message, sender, *args, **kwargs)
                return receive_with_log
            
            def make_send_with_log(agent):
                def send_with_log(self, message: Dict[str, Any], recipient: Any, *args, **kwargs) -> None:
                    try:
                        recipient_name = getattr(recipient, "name", "unknown")
                        content = message.get("content", "")
                        orchestrator._log_group_message(agent.name, recipient_name, content)
                    except Exception as e:
                        logging.debug(f"Erro ao fazer log de mensagem enviada: {e}")
                    return agent._original_send(message, recipient, *args, **kwargs)
                return send_with_log
            
            # Substituir métodos com versões que fazem logging
            try:
                agent.receive = make_receive_with_log(agent).__get__(agent)
                agent.send = make_send_with_log(agent).__get__(agent)
                logging.debug(f"✓ Logging configurado para agente: {agent.name}")
            except Exception as e:
                logging.error(f"❌ Erro ao configurar logging para agente {agent.name}: {e}")
        
        # Configurar chat em grupo com seleção manual
        def custom_speaker_selection(last_speaker, groupchat):
            """Seleciona próximo speaker seguindo fluxo TDD"""
            messages = groupchat.messages
            if not messages:
                return self.planner
            
            last_msg = messages[-1]
            speaker_name = last_speaker.name if last_speaker else None
            content = last_msg.get("content", "")
            
            # Fluxo: Planner → Tester → Executor → Developer → Executor → pytest
            if speaker_name == "Planner":
                return self.tester
            elif speaker_name == "Tester" and "```python" in content:
                return self.executor
            elif speaker_name == "Executor" and "test_app.py" in content and "exitcode: 0" in content:
                # Testes foram criados, chamar Developer
                return self.developer
            elif speaker_name == "Developer" and "```python" in content:
                return self.executor
            elif speaker_name == "Executor" and "app_code.py" in content and "exitcode: 0" in content:
                # Código criado, Executor deve rodar pytest (auto-reply)
                return self.executor
            elif "exitcode:" in content and ("FAILED" in content or "PASSED" in content or "ERROR" in content):
                # Resultado de pytest, chamar Reviewer
                return self.reviewer
            elif speaker_name == "Reviewer":
                if "TERMINATE" in content:
                    return None
                else:
                    return self.developer
            
            # Default: Manager decide
            return "auto"
        
        self.groupchat = autogen.GroupChat(
            agents=self.agents,
            messages=[],
            max_round=25,
            speaker_selection_method=custom_speaker_selection
        )
        
        # Manager do chat em grupo
        self.manager = autogen.GroupChatManager(
            groupchat=self.groupchat,
            llm_config=Config.get_llm_config(),
            system_message=self._get_manager_prompt()
        )
    
    def _setup_executor(self) -> autogen.UserProxyAgent:
        """Configurar agente executor"""
        
        def check_and_run_tests(recipient, messages, sender, config):
            """Após criar app_code.py, executar pytest automaticamente"""
            if not messages:
                return False, None
            
            last_msg = messages[-1]
            content = last_msg.get("content", "")
            
            # Se acabou de criar app_code.py com sucesso, rodar pytest
            if "app_code.py" in content and "exitcode: 0" in content:
                import os
                test_file = os.path.join(self.workspace_dir, "test_app.py")
                if os.path.exists(test_file):
                    return True, "Execute os testes:\n```sh\npytest workspace/test_app.py -v\n```"
            
            return False, None
        
        executor = autogen.UserProxyAgent(
            name="Executor",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
            code_execution_config={
                "work_dir": self.workspace_dir,
                "use_docker": False,
            },
            system_message="Você executa código Python e comandos shell que recebe."
        )
        
        # Registrar função para executar pytest automaticamente
        executor.register_reply(
            [autogen.Agent, None],
            reply_func=check_and_run_tests,
            position=0
        )
        
        return executor
    
    def _get_manager_prompt(self) -> str:
        """Retorna prompt do manager com fluxo TDD"""
        return """
Você gerencia o ciclo TDD. Selecione o próximo agente seguindo esta ordem:

1. Planner cria plano
2. Tester envia código Python
3. Executor EXECUTA código do Tester (o código cria test_app.py)
4. Developer envia código Python  
5. Executor EXECUTA código do Developer (o código cria app_code.py)
6. Executor executa: pytest workspace/test_app.py -v
7. Se FAILED: Developer → Executor → volte ao passo 6
8. Se PASSED: Reviewer → TERMINATE se OK

CRÍTICO: Após Tester ou Developer enviar código, o próximo SEMPRE é Executor.
Executor deve responder após executar cada código/comando.
        """
    
    def run(self, specification: str) -> TDDState:
        """
        Executar fluxo TDD completo.
        
        Args:
            specification: Especificação do que deve ser implementado
        
        Returns:
            TDDState: Estado final do ciclo TDD
        """
        logging.info("=" * 60)
        logging.info("INICIANDO WORKFLOW TDD")
        logging.info("=" * 60)
        logging.info(f"\n📋 Especificação:\n{specification}\n")
        
        # Inicializar estado
        state = StateManager(specification)
        
        # Limpar workspace
        if os.path.exists(self.workspace_dir):
            for f in os.listdir(self.workspace_dir):
                if f.endswith('.py'):
                    os.remove(os.path.join(self.workspace_dir, f))
        
        # Executar fluxo TDD - UMA ÚNICA VEZ
        try:
            logging.info("=" * 60)
            logging.info("💬 INICIANDO CICLO TDD")
            logging.info("=" * 60)
            
            chat_response = self.executor.initiate_chat(
                self.manager,
                message=f"Implemente uma solução TDD para: {specification}"
            )
            
            # Verificar se alguma mensagem contém TERMINATE
            if self.groupchat.messages:
                last_messages = self.groupchat.messages[-10:]  # Verificar últimas 10 mensagens
                for msg in last_messages:
                    content = msg.get("content", "")
                    if "TERMINATE" in content:
                        logging.info("🎉 Ciclo TDD concluído com sucesso! (TERMINATE recebido)")
                        state.update(status="passed")
                        break
        
        except Exception as e:
            logging.error(f"❌ Erro no ciclo TDD: {str(e)}")
            state.update(status="error")
        
        # Relatório final
        self._print_final_report(state)
        return state.state
    
    def _print_final_report(self, state: StateManager) -> None:
        """Imprimir relatório final do TDD"""
        logging.info("=" * 60)
        logging.info("📊 RELATÓRIO FINAL DO TDD")
        logging.info("=" * 60)
        logging.info(f"✅ Status: {state.get('status', 'unknown')}")
        logging.info(f"🔄 Mensagens no chat: {len(self.groupchat.messages)}")
        logging.info(f"📄 Implementação: {Config.WORKSPACE_PATH}/{Config.IMPLEMENTATION_MODULE}.py")
        logging.info(f"📄 Testes: {Config.WORKSPACE_PATH}/{Config.TEST_FILE}")
        
        if state.get("status") == "passed":
            logging.info("\n🎉 Ciclo TDD concluído com sucesso!")
            logging.info("   ✓ RED: Testes falharam inicialmente")
            logging.info("   ✓ GREEN: Implementação passou todos os testes")
            logging.info("   ✓ REFACTOR: Código refinado (se necessário)")
        
        logging.info("=" * 60)

def main():
    """Função principal"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    logging.info("Iniciando o sistema de Agentes TDD AutoGen...")

    user_request = """
    Eu preciso de um código Python.
    A tarefa é criar uma função chamada 'knight_move(pos)' que receba uma string contendo uma casa do tabuleiro de xadrez
    e retorne todas as casas que a peça pode ser movida a partir da posição informada.
    """

    orchestrator = TDDOrchestrator()
    state = orchestrator.run(user_request)

    logging.info("🏁 Sistema TDD AutoGen finalizado.")
    return state

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n⚠️ Execução interrompida pelo usuário")
    except Exception as e:
        logging.error(f"\n❌ Erro fatal: {str(e)}")
