import os
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
from streamlit_chat import message
from prompt import SUGGESTIONS_AGENT_SYSTEM_PROMPT, SYSTEM_PROMPT, QUALIFICATION_QUESTIONS
from translations import *
import requests
import json
from datetime import datetime, timedelta

load_dotenv()

# Setting page title and header
st.set_page_config(page_title="Sira Logic AI", page_icon=":robot_face:")
st.markdown("<h2 style='text-align: center;'>Sira Logic - AI Assitant</h1>", unsafe_allow_html=True)

# Create OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# GHL API Configuration
API_KEY = os.getenv('API_KEY')
GHL_API_KEY = os.getenv('GHL_API_KEY')
GHL_LOCATION_ID = os.getenv('GHL_LOCATION_ID')
GHL_API_BASE_URL = "https://rest.gohighlevel.com/v1"
GHL_API_BASE_URL_NEW = "https://services.leadconnectorhq.com"
CALENDAR_ID = "CVokAlI8fgw4WYWoCtQz"

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
if 'lead_qualification_stage' not in st.session_state:
    st.session_state['lead_qualification_stage'] = 0
if 'lead_responses' not in st.session_state:
    st.session_state['lead_responses'] = {}
if 'lead_score' not in st.session_state:
    st.session_state['lead_score'] = "new"
if 'ghl_contact_id' not in st.session_state:
    st.session_state['ghl_contact_id'] = None
if 'business_name' not in st.session_state:
    st.session_state['business_name'] = ""
if 'phone' not in st.session_state:
    st.session_state['phone'] = ""

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


# GHL integration functions
def create_ghl_contact(name, email, phone="", business_name=""):
    """Create a new contact in GoHighLevel CRM"""
    try:
        if not GHL_API_KEY or not GHL_LOCATION_ID:
            st.error("GHL API credentials are missing. Please check your environment variables.")
            return None

        headers = {
            "Authorization": f"Bearer {GHL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print(f"Sending request to GHL API for contact: {email}")
        
        data = {
            "email": email,
            "name": name,
            "phone": phone,
            "companyName": business_name,
            "locationId": GHL_LOCATION_ID,
            "tags": ["chatbot-lead"]
        }
        
        response = requests.post(
            f"{GHL_API_BASE_URL}/contacts", 
            headers=headers,
            json=data
        )
        
        # Log the response status and content
        print(f"GHL API Response Status: {response.status_code}")
        print(f"GHL API Response Content: {response.text}")
        
        if response.status_code == 200:
            contact_data = response.json()
            if 'contact' in contact_data and 'id' in contact_data['contact']:
                st.success(f"Successfully created contact in GHL for {email}")
                return contact_data['contact']['id']
            else:
                st.error("Unexpected response format from GHL API")
                return None
        else:
            error_message = f"Failed to create contact in GHL. Status: {response.status_code}, Error: {response.text}"
            st.error(error_message)
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while contacting GHL API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error while creating contact: {str(e)}")
        return None

def update_ghl_contact(contact_id, data):
    """Update an existing contact in GoHighLevel CRM"""
    try:
        if not GHL_API_KEY:
            st.error("GHL API key is missing. Please check your environment variables.")
            return False

        headers = {
            "Authorization": f"Bearer {GHL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print(f"Updating GHL contact {contact_id}")
        
        response = requests.put(
            f"{GHL_API_BASE_URL}/contacts/{contact_id}", 
            headers=headers,
            json=data
        )
        
        print(f"GHL API Update Response Status: {response.status_code}")
        print(f"GHL API Update Response Content: {response.text}")
        
        if response.status_code == 200:
            st.success(f"Successfully updated contact in GHL")
            return True
        else:
            st.error(f"Failed to update contact in GHL: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while updating GHL contact: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Unexpected error while updating contact: {str(e)}")
        return False
    
def add_note_to_ghl_contact(contact_id, note):
    """Add a note to a contact in GoHighLevel CRM"""
    try:
        if not GHL_API_KEY:
            st.error("GHL API key is missing. Please check your environment variables.")
            return False

        headers = {
            "Authorization": f"Bearer {GHL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "body": note,
            "contactId": contact_id,
            "locationId": GHL_LOCATION_ID  # Add locationId to the request
        }
        
        print(f"Adding note to GHL contact {contact_id}")
        
        response = requests.post(
            f"{GHL_API_BASE_URL}/contacts/{contact_id}/notes/", 
            headers=headers,
            json=data
        )
        
        print(f"GHL API Note Response Status: {response.status_code}")
        print(f"GHL API Note Response Content: {response.text}")
        
        if response.status_code == 200:
            st.success(f"Successfully added note to contact in GHL")
            return True
        else:
            st.error(f"Failed to add note in GHL: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while adding note to GHL contact: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Unexpected error while adding note: {str(e)}")
        return False
    
def create_ghl_calendar_appointment(contact_id, title, start_time, end_time, description=""):
    """Create a calendar appointment in GoHighLevel CRM"""
    try:
        if not API_KEY:
            st.error("GHL API key is missing. Please check your environment variables.")
            return False

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Version": "2021-04-15",
            "Content-Type": "application/json"
        }
        
        # Format the date and time properly for GHL
        # start_datetime = datetime.fromisoformat(start_time)
        # end_datetime = datetime.fromisoformat(end_time)
        
        data = {
            "calendarId": "iVlTvp2urxTWEEF6Lfx2",
            "locationId": "GHL_LOCATION_ID",
            "contactId": contact_id,
            "startTime": "2025-04-17T11:30:00+05:30" # You might want to make this configurable          
        }
        
        print(f"Creating calendar appointment for contact {contact_id}")
        print(f"Appointment data: {json.dumps(data, indent=2)}")
        
        response = requests.post(
            f"{GHL_API_BASE_URL_NEW}/calendars/events/appointments", 
            headers=headers,
            json=data
        )
        
        print(f"GHL API Calendar Response Status: {response.status_code}")
        print(f"GHL API Calendar Response Content: {response.text}")
        
        if response.status_code == 200:
            st.success(f"Successfully scheduled appointment in GHL")
            
            # Add a note about the appointment
            appointment_note = f"Appointment scheduled:\nTitle: {title}\nDate: {start_datetime.strftime('%Y-%m-%d')}\nTime: {start_datetime.strftime('%I:%M %p')} - {end_datetime.strftime('%I:%M %p')}\nDescription: {description}\nStatus: Scheduled\nCalendar: Sales Team\nAppointment Owner: AI Assistant"
            add_note_to_ghl_contact(contact_id, appointment_note)
            
            return True
        else:
            st.error(f"Failed to schedule appointment in GHL: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while creating appointment: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Unexpected error while creating appointment: {str(e)}")
        print(f"Detailed error: {str(e)}")  # More detailed error logging
        return False


def update_ghl_lead_score(contact_id, lead_score):
    """Update lead score and add appropriate tags"""
    tags = ["chatbot-lead"]
    
    if lead_score == "hot":
        tags.append("hot-lead")
    elif lead_score == "warm":
        tags.append("warm-lead")
    elif lead_score == "cold":
        tags.append("cold-lead")
    
    data = {
        "tags": tags,
        "customField": {
            "Lead Score": lead_score
        }
    }
    
    update_ghl_contact(contact_id, data)

def analyze_lead(responses):
    """Analyze lead responses to determine qualification score"""
    analyze_prompt = f"""
    You are a lead qualification assistant. Analyze the user's responses to the following questions and categorize them into one of these: cold (Not a good fit), warm (Potentially interested), or hot (Highly interested and ready).

    Question 1: "What's your main goal with AI automation?"
    User Response: "{responses.get('q1', 'No response')}"

    Question 2: "Have you tried any automation tools before?"
    User Response: "{responses.get('q2', 'No response')}"

    Provide ONLY the category (cold, warm, or hot) with no additional text.
    """
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a lead qualification assistant."},
            {"role": "user", "content": analyze_prompt},
        ],
    )
    result = completion.choices[0].message.content.strip().lower()
    
    # Ensure we only get one of our expected categories
    if result not in ["cold", "warm", "hot"]:
        # Default to warm if we get an unexpected response
        result = "warm"
    
    return result

def parse_appointment_time(user_input):
    """Parse appointment time from user input"""
    try:
        user_input = user_input.lower()
        now = datetime.now()
        
        # Default to 10 AM
        hour = 10
        minute = 0
        
        # Parse time if specified
        if "am" in user_input or "pm" in user_input:
            time_parts = [part for part in user_input.split() if ":" in part or "am" in part.lower() or "pm" in part.lower()]
            if time_parts:
                time_str = time_parts[0]
                if ":" in time_str:
                    hour_str, minute_str = time_str.replace("am", "").replace("pm", "").split(":")
                    hour = int(hour_str)
                    minute = int(minute_str)
                else:
                    hour = int(time_str.replace("am", "").replace("pm", ""))
                
                if "pm" in user_input and hour < 12:
                    hour += 12
        
        # Parse date
        if "tomorrow" in user_input:
            target_date = now + timedelta(days=1)
        elif "next week" in user_input:
            target_date = now + timedelta(days=7)
        elif "today" in user_input:
            target_date = now
        else:
            # Default to tomorrow if no date specified
            target_date = now + timedelta(days=1)
        
        # Combine date and time
        start_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the time has already passed today, move to tomorrow
        if start_time < now:
            start_time += timedelta(days=1)
        
        # End time is 1 hour later
        end_time = start_time + timedelta(hours=1)
        
        return start_time.isoformat(), end_time.isoformat()
    except Exception as e:
        print(f"Error parsing appointment time: {str(e)}")
        return None, None

def get_ghl_booked_slots():
    """Get booked calendar slots from GoHighLevel"""
    try:
        if not GHL_API_KEY:
            st.error("GHL API key is missing. Please check your environment variables.")
            return []

        headers = {
            "Authorization": f"Bearer {GHL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Get appointments for the next 7 days
        start_time = datetime.now()
        end_time = start_time + timedelta(days=7)
        
        params = {
            "locationId": GHL_LOCATION_ID,
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000)
        }
        
        response = requests.get(
            f"{GHL_API_BASE_URL}/appointments/slots",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            appointments = response.json().get('appointments', [])
            booked_slots = []
            for appointment in appointments:
                start = datetime.fromtimestamp(appointment['startTime'] / 1000)
                end = datetime.fromtimestamp(appointment['endTime'] / 1000)
                booked_slots.append((start, end))
            return booked_slots
        else:
            st.error(f"Failed to get appointments: {response.text}")
            return []
            
    except Exception as e:
        st.error(f"Error getting booked slots: {str(e)}")
        return []

def suggest_available_slot(booked_slots):
    """Suggest the next available time slot"""
    now = datetime.now()
    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)  # Start at 9 AM
    
    if start_time < now:
        start_time += timedelta(days=1)  # If it's past 9 AM, look at tomorrow
    
    while True:
        if start_time.hour >= 17:  # Past business hours (5 PM)
            start_time = (start_time + timedelta(days=1)).replace(hour=9, minute=0)  # Next day 9 AM
            continue
            
        if start_time.weekday() >= 5:  # Weekend
            start_time = (start_time + timedelta(days=1)).replace(hour=9, minute=0)  # Next day 9 AM
            continue
            
        end_time = start_time + timedelta(hours=1)
        slot_available = True
        
        for booked_start, booked_end in booked_slots:
            if (start_time >= booked_start and start_time < booked_end) or \
               (end_time > booked_start and end_time <= booked_end):
                slot_available = False
                break
                
        if slot_available:
            return start_time, end_time
            
        start_time += timedelta(hours=1)

def analyze_booking_intent(user_input):
    """Use LLM to analyze if user wants to book and extract time information"""
    analyze_prompt = f"""
    Analyze the user's message for appointment booking intent and time preferences.
    
    User message: "{user_input}"
    
    Provide your analysis in the following JSON format:
    {{
        "has_booking_intent": true/false,
        "time_mentioned": true/false,
        "wants_suggestion": true/false,
        "explanation": "brief explanation of your analysis"
    }}
    
    Only respond with the JSON object, no other text.
    """
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an appointment scheduling assistant."},
            {"role": "user", "content": analyze_prompt},
        ],
    )
    
    try:
        result = json.loads(completion.choices[0].message.content.strip())
        return result
    except:
        return {
            "has_booking_intent": False,
            "time_mentioned": False,
            "wants_suggestion": False,
            "explanation": "Error parsing response"
        }

def handle_lead_qualification(user_input):
    """Process the lead qualification flow"""
    current_stage = st.session_state['lead_qualification_stage']
    
    # Store the user's response to the current question
    if current_stage > 0:
        st.session_state['lead_responses'][f'q{current_stage}'] = user_input
    
    # First time creating contact in GHL
    if current_stage == 0 and st.session_state['ghl_contact_id'] is None:
        contact_id = create_ghl_contact(
            st.session_state['full_name'], 
            st.session_state['email'],
            st.session_state['phone'],
            st.session_state['business_name']
        )
        if contact_id:
            st.session_state['ghl_contact_id'] = contact_id
    
    # Increment stage for next question
    st.session_state['lead_qualification_stage'] += 1
    current_stage = st.session_state['lead_qualification_stage']
    
    # If we've gone through 2 questions, analyze the lead
    if current_stage > 2:
        lead_score = analyze_lead(st.session_state['lead_responses'])
        st.session_state['lead_score'] = lead_score
        
        # Update lead score in GHL
        if st.session_state['ghl_contact_id']:
            update_ghl_lead_score(st.session_state['ghl_contact_id'], lead_score)
            
            # Add responses as notes
            note = f"Lead Qualification Responses:\n\n"
            for q_num, response in st.session_state['lead_responses'].items():
                question_index = int(q_num[1:]) - 1
                note += f"Q: {QUALIFICATION_QUESTIONS[question_index]}\n"
                note += f"A: {response}\n\n"
            note += f"Lead Score: {lead_score}"
            
            add_note_to_ghl_contact(st.session_state['ghl_contact_id'], note)
    
    # Return the next question or finishing message
    if current_stage <= len(QUALIFICATION_QUESTIONS):
        return QUALIFICATION_QUESTIONS[current_stage - 1]
    else:
        if st.session_state['lead_score'] == "hot":
            # If this is a response to the consultation request
            if current_stage > len(QUALIFICATION_QUESTIONS) + 1:
                # Use LLM to analyze booking intent
                intent_analysis = analyze_booking_intent(user_input)
                
                if intent_analysis["has_booking_intent"]:
                    if intent_analysis["time_mentioned"]:
                        # Try to parse the time from the user's response
                        start_time, end_time = parse_appointment_time(user_input)
                        
                        if start_time and end_time:
                            # Get booked slots and check availability
                            booked_slots = get_ghl_booked_slots()
                            start_dt = datetime.fromisoformat(start_time)
                            end_dt = datetime.fromisoformat(end_time)
                            
                            slot_available = True
                            for booked_start, booked_end in booked_slots:
                                if (start_dt >= booked_start and start_dt < booked_end) or \
                                (end_dt > booked_start and end_dt <= booked_end):
                                    slot_available = False
                                    break
                            
                            if slot_available:
                                if create_ghl_calendar_appointment(
                                    st.session_state['ghl_contact_id'],
                                    "AI Automation Consultation",
                                    start_time,
                                    end_time,
                                    f"Consultation with {st.session_state['full_name']} about AI automation solutions.\n\nBusiness: {st.session_state['business_name']}\nPhone: {st.session_state['phone']}\nEmail: {st.session_state['email']}"
                                ):
                                    return f"Perfect! I've scheduled your consultation for {start_dt.strftime('%A, %B %d at %I:%M %p')}. You'll receive a confirmation email shortly with the meeting details. Is there anything else you'd like to know about our services?"
                            else:
                                # Suggest next available slot
                                next_start, next_end = suggest_available_slot(booked_slots)
                                return f"I apologize, but that time slot is already booked. The next available slot I have is {next_start.strftime('%A, %B %d at %I:%M %p')}. Would that work for you?"
                    elif intent_analysis["wants_suggestion"]:
                        # User wants a time suggestion
                        booked_slots = get_ghl_booked_slots()
                        next_start, next_end = suggest_available_slot(booked_slots)
                        return f"I can help you schedule a consultation. Would {next_start.strftime('%A, %B %d at %I:%M %p')} work for you?"
                    else:
                        return "I can help you schedule a consultation call. When would be a good time for you? I'm available on weekdays between 9 AM and 5 PM."
                else:
                    # No booking intent detected, continue normal conversation
                    return "Would you like to schedule a consultation call to discuss how we can help with your AI automation needs? I'm available on weekdays between 9 AM and 5 PM."
            
            return "I'd be happy to set up a consultation call to discuss how we can help with your AI automation needs. When would be a good time for you? I'm available on weekdays between 9 AM and 5 PM."
        elif st.session_state['lead_score'] == "warm":
            return "Thank you for sharing. Would you like to receive our case study on how AI automation has helped businesses similar to yours?"
        else:
            return "Thank you for your time. We'll keep you updated on new tools that might better match your needs in the future."




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
     # Check if we're in the lead qualification process
    if user_form_submitted() and st.session_state['lead_qualification_stage'] < 4:
        # Handle the lead qualification flow
        bot_response = handle_lead_qualification(user_input)
        st.session_state['past'].append(user_input)
        st.session_state['generated'].append(bot_response)
        st.session_state['model_name'].append(model_name)
        
        # Generate suggestions based on the current qualification stage
        if st.session_state['lead_qualification_stage'] == 1:
            suggestions = ["Generate more leads", "Improve outreach", "Automate social media", "All of the above"]
        elif st.session_state['lead_qualification_stage'] == 2:
            suggestions = ["Yes, tried some tools", "No, this is new to me", "Using basic automation only", "Looking for better solutions"]
        elif st.session_state['lead_qualification_stage'] == 3:
            suggestions = ["Yes, I'd like a consultation", "Not at this time", "Send me more information first", "How much does it cost?"]
        else:
            suggestions = generate_suggestions(bot_response, user_input)
        
        st.session_state['suggestions'] = suggestions
        return bot_response, suggestions
    else:
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

        # If the contact exists in GHL, add this conversation as a note
        if st.session_state['ghl_contact_id']:
            note = f"Chat conversation:\nUser: {user_input}\nBot: {output}"
            add_note_to_ghl_contact(st.session_state['ghl_contact_id'], note)
        
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
