import os
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
from streamlit_chat import message
from prompt import SUGGESTIONS_AGENT_SYSTEM_PROMPT, SYSTEM_PROMPT
from translations import *

load_dotenv()

# Setting page title and header
st.set_page_config(page_title="Sira Logic AI", page_icon=":robot_face:")
st.markdown("<h2 style='text-align: center;'>Sira Logic - AI Assitant</h1>", unsafe_allow_html=True)

# Create OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialise session state variables
if 'generated' not in st.session_state:
    st.session_state['generated'] = []
if 'past' not in st.session_state:
    st.session_state['past'] = []
if 'messages' not in st.session_state:
    st.session_state['messages'] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
if 'suggestions' not in st.session_state:
    st.session_state['suggestions'] = []
if 'model_name' not in st.session_state:
    st.session_state['model_name'] = []
if 'cost' not in st.session_state:
    st.session_state['cost'] = []
if 'total_tokens' not in st.session_state:
    st.session_state['total_tokens'] = []
if 'total_cost' not in st.session_state:
    st.session_state['total_cost'] = 0.0
if 'full_name' not in st.session_state:
    st.session_state['full_name'] = ""
if 'email' not in st.session_state:
    st.session_state['email'] = ""
if 'agreed' not in st.session_state:
    st.session_state['agreed'] = False

# Sidebar - let user choose model, show total cost of current conversation, and let user clear the current conversation
st.sidebar.title("Sidebar")
model_name = st.sidebar.radio("Choose a model:", ("GPT-4o", "GPT-4o-Mini", "GPT-4-Turbo", "GPT-3.5", "O1-Preview"))
language = st.sidebar.selectbox("Choose a language:", ("English", "Danish"))
counter_placeholder = st.sidebar.empty()
counter_placeholder.write(f"Total cost of this conversation: ${st.session_state['total_cost']:.5f}")
clear_button = st.sidebar.button("Clear Conversation", key="clear")

if language == "Danish":
    labels = translations["Danish"]
else:
    labels = translations["English"]

initial_suggestions = labels["Suggestions"]
message(labels['Welcome Message'], key=str('-1'), allow_html=True)

# Map model names to OpenAI model IDs
if model_name == "GPT-4o":
    model = "gpt-4o"
elif model_name == "GPT-4o-Mini":
    model = "gpt-4o-mini"
elif model_name == "GPT-3.5":
    model = "gpt-3.5-turbo"
elif model_name == "GPT-4-Turbo":
    model = "gpt-4-turbo"
elif model_name == "O1-Preview":
    model = "o1-preview"

# reset everything
if clear_button:
    st.session_state['generated'] = []
    st.session_state['past'] = []
    st.session_state['messages'] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    st.session_state['suggestions'] = []
    st.session_state['number_tokens'] = []
    st.session_state['model_name'] = []
    st.session_state['cost'] = []
    st.session_state['total_cost'] = 0.0
    st.session_state['total_tokens'] = []
    st.session_state['full_name'] = ""
    st.session_state['email'] = ""
    st.session_state['agreed'] = False
    counter_placeholder.write(f"Total cost of this conversation: ${st.session_state['total_cost']:.5f}")


# generate a response
def generate_response(prompt):
    st.session_state['messages'].append({"role": "user", "content": prompt})
    completion = client.chat.completions.create(
        model=model,
        messages=st.session_state['messages']
    )
    response = completion.choices[0].message.content
    st.session_state['messages'].append({"role": "assistant", "content": response})
    total_tokens = completion.usage.total_tokens
    prompt_tokens = completion.usage.prompt_tokens
    completion_tokens = completion.usage.completion_tokens
    return response, total_tokens, prompt_tokens, completion_tokens

# generate suggestions
def generate_suggestions(agent_prompt, user_prompt):
    completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {"role": "system", "content": SUGGESTIONS_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
User's Query:
{user_prompt}

AI Agent's Response:
{agent_prompt}

Next Possible Queriees from User:
""",
            },
        ],
    )
    response = completion.choices[0].message.content
    suggestions =  [
        line[2:] for line in response.split("\n") if line.strip()
    ]
    return suggestions

def update_chat_response_state(user_input):
    output, total_tokens, prompt_tokens, completion_tokens = generate_response(user_input)
    st.session_state['past'].append(user_input)
    st.session_state['generated'].append(output)
    st.session_state['model_name'].append(model_name)
    st.session_state['total_tokens'].append(total_tokens)
    suggestions = generate_suggestions(output, user_input)
    st.session_state['suggestions'] = suggestions
    # from https://platform.openai.com/docs/pricing
    if model_name == "GPT-4o": # Input: US$0.005 / 1K | Output: US$0.015 / 1K
        cost = ((prompt_tokens * 0.005) + (completion_tokens * 0.015)) / 1000
    elif model_name == "GPT-4o-Mini": # Input: US$0.00015 / 1K | Output: US$0.0006 / 1K
        cost = ((prompt_tokens * 0.0005) + (completion_tokens * 0.0015)) / 1000
    elif model_name == "GPT-3.5": # Input: US$0.003 / 1K | Output: US$0.006 / 1K
        cost = ((prompt_tokens * 0.003) + (completion_tokens * 0.006)) / 1000
    elif model_name == "GPT-4-Turbo": # Input: US$0.01 / 1K | Output: US$0.03 / 1K
        cost = ((prompt_tokens * 0.01) + (completion_tokens * 0.03)) / 1000
    elif model_name == "O1-Preview": # Input: US$0.002 / 1K | Output: US$0.006 / 1K
        cost = ((prompt_tokens * 0.002) + (completion_tokens * 0.006)) / 1000
    st.session_state['cost'].append(cost)
    st.session_state['total_cost'] += cost
    return output, suggestions

def user_form_submitted():
    return st.session_state["full_name"] and st.session_state["email"] and st.session_state["agreed"]

if not user_form_submitted():
    with st.form("details_form"):
        st.write(labels["user_acknowledgement_message"])
        full_name_val = st.text_input(labels["Full Name"])
        email_val = st.text_input(labels["Email"])
        checkbox_val = st.checkbox(labels["I agree to the terms and conditions"])

        # Every form must have a submit button.
        submitted = st.form_submit_button(labels["Submit"])
        if submitted:
            st.session_state["full_name"] = full_name_val
            st.session_state["email"] = email_val
            st.session_state["agreed"] = checkbox_val
            st.session_state["suggestions"] = initial_suggestions
            st.write(labels["Hello User"].format(full_name=st.session_state['full_name']))
else:
    message(str(labels["Hello User"]).format(full_name=st.session_state['full_name']), key=str('-2'), allow_html=True)

# container for chat history
response_container = st.container()
# container for text box
container = st.container()
# container for suggestions
suggestions_container = st.container()

if user_form_submitted():
    with container:
        with st.form(key='my_form', clear_on_submit=True):
            user_input = st.text_input(labels["You:"], key='input')
            submit_button = st.form_submit_button(label=labels["Submit"])

        if submit_button and user_input:
            update_chat_response_state(user_input)

if user_form_submitted():
    if st.session_state['suggestions']:
        with suggestions_container:
            for suggestion in st.session_state['suggestions']:
                # click on suggestion to send it to the chat
                st.button(
                    label=suggestion,
                    on_click=lambda s=suggestion: update_chat_response_state(s),
                )

if st.session_state['generated']:
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user')
            generated_message = st.session_state["generated"][i]
            message(generated_message, key=str(i), allow_html=True)
            counter_placeholder.write(f"Total cost of this conversation: ${st.session_state['total_cost']:.5f}")
