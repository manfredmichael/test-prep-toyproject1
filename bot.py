from langchain.agents import agent_types, initialize_agent, create_structured_chat_agent, AgentType, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain_community.llms import Replicate
from langchain_core.tools import tool
from langchain import hub

from dotenv import load_dotenv
import streamlit as st
import requests
import os
import json

import sqlite3
from datetime import datetime, timedelta
import random
from langchain.agents import tool

# Setup SQLite
conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

# Create table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    vehicle_type TEXT,
    brand_code TEXT,
    model_code TEXT,
    year_code TEXT,
    order_date TEXT,
    delivery_date TEXT
)
""")
conn.commit()



def parse_input(input_str):
    parts = input_str.split(";")
    return dict(part.split("=") for part in parts)




@tool
def multiply(input: str) -> str:
    """
    Multiply two numbers.
    Input format: 'a=123;b=213'
    """
    try:
        # parts = input.strip().split(" and ")
        # a, b = int(parts[0]), int(parts[1])
        input_dict = parse_input(input)
        a = float(input_dict['a'])
        b = float(input_dict['b'])
        return str(a * b)
    except Exception as e:
        return f"Something went wrong with the tool: {e}"

@tool
def get_weather(input: str) -> str:
    """Get current weather for given latitude & longitude.

    Use a search tool to get the city coordinates first before using this tool to get accurate & updated weather..

    Input format: 'lat=-6.2;lon=106.8'
    """

    try:
      # parts = input.strip().split(" and ")
      # lat, lon = parts[0], parts[1]
      input_dict = parse_input(input)
      lat = float(input_dict['lat'])
      lon = float(input_dict['lon'])
      response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true")
      result = response.json()
      return result
    except Exception as e:
      return f"Something went wrong with the tool: {e}"


@tool
def cat_fact(input):
    """Get unique and random cat fact"""
    try:
      response = requests.get("https://catfact.ninja/fact?max_length=200")

      return response.json()['fact']
    except Exception as e:
      return f"Something went wrong with the tool: {e}"



@tool
def get_brands_str(input_str: str) -> dict:
    """Get brands for a type of vehicle

    Input: 'vehicle_type=carros' (options: carros, motos, caminhoes)"""
    try:
        params = parse_input(input_str)
        vt = params["vehicle_type"]
        limit = int(params.get("limit", 20))  # default: 10
        url = f"https://parallelum.com.br/fipe/api/v1/{vt}/marcas"
        data = requests.get(url).json()
        return json.dumps(data[:limit], ensure_ascii=False)
    except Exception as e:
        return {"error": str(e)}


@tool
def get_models_and_years_tool(input_str: str) -> dict:
    """Get vehicle model & year. Requires brand_code.

    Input: 'vehicle_type=carros;brand_code=7'
    """
    try:
        import time
        params = parse_input(input_str)
        vt = params["vehicle_type"]
        brand_code = params["brand_code"]
        limit = int(params.get("limit", 2))

        # Step 1: Get models
        models_url = f"https://parallelum.com.br/fipe/api/v1/{vt}/marcas/{brand_code}/modelos"
        models_data = requests.get(models_url).json()
        modelos = models_data.get("modelos", [])[:limit]

        # Step 2: For each model, get available years
        result = []
        html_blocks = []

        for model in modelos:
            model_name = model['nome']
            model_code = model['codigo']

            years_url = f"https://parallelum.com.br/fipe/api/v1/{vt}/marcas/{brand_code}/modelos/{model_code}/anos"
            years_data = requests.get(years_url).json()[:limit]

            # Prepare display
            html_blocks.append(
              f"<b>🚗 {model_name}</b> (<code>{model_code}</code>)<br>"
              f"📅 Available years: " +
              ", ".join([f"{y['nome']} (<code>{y['codigo']}</code>)" for y in years_data]) +
              "<br><br>"
            )

            result.append({
                "model_name": model_name,
                "model_code": model_code,
                "years": years_data
            })

            time.sleep(0.2)  # prevent hitting rate limit

        return "\n".join(html_blocks)

    except Exception as e:
        return {"error": str(e)}

# Tool: Place an order
@tool
def order_vehicle(input_str: str) -> str:
    """
    Place a vehicle order. Requires vehicle_type, brand_code, model_code, year_code, and customer_name.

    Input: 'customer_name=<customer_name>;vehicle_type=carros;brand_code=21;model_code=4828;year_code=2020-3'
    """
    try:
        params = dict(pair.split("=") for pair in input_str.split(";") if "=" in pair)
        name = params["customer_name"]
        vt = params["vehicle_type"]
        brand = params["brand_code"]
        model = params["model_code"]
        year = params["year_code"]

        order_date = datetime.now()
        delivery_days = random.randint(5, 14)
        delivery_date = order_date + timedelta(days=delivery_days)

        cursor.execute("""
            INSERT INTO orders (customer_name, vehicle_type, brand_code, model_code, year_code, order_date, delivery_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, vt, brand, model, year, order_date.isoformat(), delivery_date.isoformat()))
        conn.commit()

        return f"✅ Order placed for {name}! Estimated delivery: {delivery_date.date()}."
    except Exception as e:
        return f"❌ Error placing order: {str(e)}"



@tool
def view_orders(input: str = "") -> str:
    """
    Gets all placed orders.

    Input: 'customer_name=<customer_name>'
    """
    cursor.execute("SELECT customer_name, vehicle_type, brand_code, model_code, year_code, delivery_date FROM orders")
    rows = cursor.fetchall()

    if not rows:
        return "<i>No orders found.</i>"

    html_blocks = []
    for row in rows:
        customer, vtype, brand, model, year, delivery = row
        html = f"""
        <div style="
              background-color: #fdfdfd;
              border: 1px solid #e4e4e4;
              border-radius: 10px;
              padding: 18px 22px;
              margin-bottom: 16px;
              font-family: 'Segoe UI', sans-serif;
              font-size: 15px;
              color: #212121;
              box-shadow: 0 2px 8px rgba(0,0,0,0.04);">

            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
              <div style="font-size: 16px; font-weight: 600;">🧾 {customer}</div>
              <div style="font-size: 13px; color: #757575;">Order ID #AUTO</div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; row-gap: 4px;">
              <div>🚗 <b>Type</b>: {vtype}</div>
              <div>📦 <b>Brand</b>: {brand}</div>
              <div>🔢 <b>Model</b>: {model}</div>
              <div>📅 <b>Year</b>: {year}</div>
            </div>

            <div style="margin-top: 10px; color: #d84315;"><b>🚚 Delivery:</b> {delivery}</div>
          </div>
        """
        html_blocks.append(html)



    return "\n".join(html_blocks) + "\n\n  Copy & Paste this HTML display into your final response!"










def build_agent():
  load_dotenv()
  # search_token = os.environ['SEARCH_TOKEN']

  llm = Replicate(
    model="anthropic/claude-3.5-haiku"
  )




  memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)


  tools = [
    # multiply,
    # search,
    # get_weather,
    # cat_fact,
    get_brands_str,
    get_models_and_years_tool,
    # get_price_str,
    order_vehicle,
    view_orders
  ]



  prompt = hub.pull("hwchase17/structured-chat-agent")

  agent = create_structured_chat_agent(llm, tools, prompt)

  agent_executor = AgentExecutor(
      agent=agent,
      tools=tools,
      memory=memory,
      verbose=True,
      max_iterations=10,
      max_execution_time=10 * 60.0,
      handle_parsing_errors=True
  )


  # agent = initialize_agent(
  #     llm=llm,
  #     tools=tools,
  #     agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
  #     agent_kwargs={"system_message": system_message},
  #     verbose=True,
  # )

  # agent = AgentExecutor.from_agent_and_tools(
  #     agent=agent.agent,
  #     tools=tools,
  #     memory=memory,
  #     verbose=True,
  #     max_iterations=10,
  #     max_execution_time=10 * 60.0,
  #     handle_parsing_errors=True
  # )

  return agent





def build_agent():
    load_dotenv()
    if "REPLICATE_API_TOKEN" in st.secrets:
        os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
   

    llm = Replicate(model="anthropic/claude-3.5-haiku")


    system_message = """
    You are a helpful assistant that uses tools to answer questions. Do not guess or invent information.

    Greet the user nicely when they greet you.

    If a user selects or confirms a vehicle brand, model, or year, use the appropriate tool immediately.

    Never say "please wait" or respond with summaries if a tool should be used instead. Your job is to solve the user's request by using tools and returning the result.

    Always call the `order_vehicle` tool to place an order — never just confirm with a message.

    Only confirm after the tool has been called and returned a successful response.

    You are not allowed to say an order has been completed unless the tool confirms it.

    Always prefer calling a tool if unsure.

    You are capable of handling vehicle orders. If a user imply an interest in purchasing a vehicle follow this step:
    1. Gain the user prefered brand -> use `get_brands_tool` to get list of brands available and the codes.
    2. Gain user preferred model -> use `get_models_and_years_tool` to get list of models based on selected brand_code.
    3. Once confirmed, use `order_vehicle` tool to insert the order

    An order is placed only when the output of the tool confirm so. Ensure you call `order_vehicle` tool correctly! has been confirmed.

    Remember to note down all important information in your reasoning process such as brand codes, model codes, year codes, etc so you don't have to call the tools over & over.

    Be careful not to hallucinate or invent tool results. Don't make up things! especially about vehicle model and years! Always check with tools or based on chat history.
    Explain your reasoning before calling a tool if the answer is uncertain.

    Format the final response nicely & professionally with new lines & bullet points. If prompted by the tool observation, return the dat with pretty HTML display."""

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )

    tools = [
        get_brands_str,
        get_models_and_years_tool,
        order_vehicle,
        view_orders
    ]

    # This is the correct conversational agent
    agent_executor = initialize_agent(
        llm=llm,
        tools=tools,
        agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
        memory=memory,
        agent_kwargs={"system_message": system_message},
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True
    )

    return agent_executor
