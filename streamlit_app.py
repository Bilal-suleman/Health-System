import streamlit as st
import requests

st.title("Prompt Refiner")

# Model selection
model = st.selectbox("Choose a model:", [
    "openchat/openchat-3.5-1210",
    "huggingfaceh4/zephyr-7b-beta",
    "mistral/mistral-7b-instruct",
    "nousresearch/nous-capybara-7b",
    "meta-llama/llama-2-13b-chat"
])

# Prompt input
user_prompt = st.text_area("Enter your prompt:")

if st.button("Refine Prompt"):
    if not user_prompt:
        st.warning("Please enter a prompt.")
    else:
        headers = {
            "Authorization": f"Bearer {st.secrets['api']['openrouter_key']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            refined = response.json()['choices'][0]['message']['content']
            st.subheader("Refined Prompt:")
            st.write(refined)
        else:
            st.error(f"Error: {response.status_code} - {response.text}")
