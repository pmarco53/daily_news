from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from IPython.display import Image, display
import gradio as gr
from langgraph.prebuilt import ToolNode, tools_condition
import requests
import os
from langchain_core.tools import Tool
import asyncio
import nest_asyncio
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

nest_asyncio.apply()

load_dotenv(override=True)

class State(TypedDict):
    
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)


# Pegue esses valores do seu arquivo .env ou variáveis de ambiente
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")      # ex: "1234567890:AAF1b2C3d4e5f6g7h8i9j0kLmNoPqRsTuVwX"
TELEGRAM_CHAT_ID    = os.getenv("CHAT_ID")        # ex: "123456789" ou "-1001987654321" (grupos)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_message(text: str):
    """Envia uma mensagem de notificação via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erro: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados!")
        return False

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"  # opcional: "HTML" ou "MarkdownV2"
    }

    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        response.raise_for_status()  # levanta exceção se não for 2xx
        return True
    except Exception as e:
        print(f"Erro ao enviar mensagem no Telegram: {e}")
        return False


# Criação da tool compatível com LangChain / LangGraph
tool_telegram = Tool(
    name="send_telegram_notification",
    func=send_telegram_message,
    description="Envia uma notificação/mensagem para o usuário via Telegram. Use quando quiser avisar ou notificar o usuário diretamente."
)# Introducing nest_asyncio
# Python async code only allows for one "event loop" processing aynchronous events.
# The `nest_asyncio` library patches this, and is used for special situations, if you need to run a nested event loop.


from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_async_playwright_browser

# If you get a NotImplementedError here or later, see the Heads Up at the top of the notebook

async_browser =  create_async_playwright_browser(headless=False)  # headful mode
toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
tools = toolkit.get_tools()

for tool in tools:
    #print(f"{tool.name}={tool}")

tool_dict = {tool.name:tool for tool in tools}

navigate_tool = tool_dict.get("navigate_browser")
extract_text_tool = tool_dict.get("extract_text")

    
async def testar_ferramentas():
    await navigate_tool.arun({"url": "https://www.cnn.com.br"})
    text = await extract_text_tool.arun({})
    
    import textwrap
    #print(textwrap.fill(text))

# Para rodar o teste:
import asyncio
asyncio.run(testar_ferramentas())

import textwrap
#print(textwrap.fill(text))

all_tools = tools + [tool_telegram]


llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(all_tools)


def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}



graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=all_tools))
graph_builder.add_conditional_edges( "chatbot", tools_condition, "tools")
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)
display(Image(graph.get_graph().draw_mermaid_png()))

config = {"configurable": {"thread_id": "10"}}

async def chat(user_input: str, history):
    result = await graph.ainvoke({"messages": [{"role": "user", "content": user_input}]}, config=config)
    return result["messages"][-1].content


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# --- Mantenha suas definições de State, Graph e Tools anteriores ---

async def executar_rotina_matinal():
    """Função que o agendador irá chamar às 08:00"""
    print(f"Iniciando consulta de notícias: {datetime.now()}")

    site = "https://techcrunch.com"
    
    # Prompt específico para o agente
    
    prompt = (
    f"Acesse a home da {site}.\n"
    "Extraia os títulos e os links das 5 notícias principais "
    "que aparecem na vitrine da página.\n"
    "Não clique nos links das notícias. Apenas leia o que está na home,\n"
    "formate uma lista e envie para o meu Telegram via tool_telegram.\n"
    "Traduza para o português"
    )

    
    try:
        # Executa o grafo com o comando automático
        inputs = {"messages": [("user", prompt)]}
        async for output in graph.astream(inputs, config=config):
            # O LangGraph irá processar as ferramentas (Navegar -> Extrair -> Telegram)
            for key, value in output.items():
                print(f"Processando nó: {key}")
    except Exception as e:
        print(f"Erro na rotina: {e}")

async def main():
    # --- TESTE MANUAL IMEDIATO ---
    #print("Executando teste inicial agora...")
    #await executar_rotina_matinal() 
    # -----------------------------

    scheduler = AsyncIOScheduler()
    scheduler.add_job(executar_rotina_matinal, 'cron', hour=8, minute=0)
    scheduler.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # Como você já usa nest_asyncio, podemos rodar o loop principal
    asyncio.run(main())