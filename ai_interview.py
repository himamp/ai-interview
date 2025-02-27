import os
import time
import sqlite3
import streamlit as st
import pandas as pd
import speech_recognition
import requests

# ✅ Step 1: Ensure OpenRouter API Key is Set Securely
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
if not openrouter_api_key:
    raise ValueError("⚠️ OpenRouter API Key is missing! Set OPENROUTER_API_KEY in your environment.")

# ✅ Step 2: OpenRouter API URL
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ✅ Step 3: Load Questions & Answers from Excel
@st.cache_data
def load_questions():
    file_path = "/Users/himamp/Documents/questions.xlsx"  # Adjust this path as needed
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"⚠️ Error: The file '{file_path}' was not found.")

    df = pd.read_excel(file_path)
    df.rename(columns=lambda x: x.strip(), inplace=True)  # Strip column names

    if "Question" not in df.columns or "Answer" not in df.columns:
        raise KeyError(f"⚠️ Error: Expected columns 'Question' and 'Answer', but found: {df.columns.tolist()}")

    return df

# ✅ Step 4: Transcribe Audio Using Google Speech Recognition
def transcribe_audio(audio_data):
    recognizer = sr.Recognizer()
    
    try:
        response_text = recognizer.recognize_google(audio_data)
        return response_text.strip()
    except sr.UnknownValueError:
        print("❌ Google Speech-to-Text could not understand the audio")
        return ""
    except sr.RequestError:
        print("❌ Could not request results from Google Speech-to-Text")
        return ""

# ✅ Step 5: AI-based Answer Scoring with OpenRouter (GPT-4o)
def score_response(user_answer, correct_answer, use_ai=True):
    if use_ai:
        prompt = f"""
        You are an interview evaluator. Compare the candidate's response to the correct answer.
        - Candidate Response: {user_answer}
        - Model Answer: {correct_answer}
        Give a score **between 0-10** based on relevance, completeness, and correctness.
        **Only return a numeric score between 0-10** with no extra text.
        """

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "openai/gpt-4o",  # Change to "mistral/mixtral" or "anthropic/claude-3-opus" if needed
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": 5
        }

        response = requests.post(OPENROUTER_URL, json=data, headers=headers)

        if response.status_code == 200:
            result = response.json()
            score_text = result["choices"][0]["message"]["content"].strip()

            try:
                score = int(score_text)
                return min(max(score, 0), 10)  # Ensure it's between 0-10
            except ValueError:
                print(f"⚠️ Unexpected AI response: {score_text}")
                return 0  # Default to 0 if AI gives non-numeric output
        else:
            print(f"❌ OpenRouter API Error: {response.status_code} - {response.text}")
            return 0

    return 10 if user_answer.lower().strip() == correct_answer.lower().strip() else 0

# ✅ Step 6: Save Results to SQLite Database
def save_results(candidate_name, responses):
    conn = sqlite3.connect("interviews.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS results (name TEXT, question TEXT, response TEXT, score INTEGER)")
    for question, (response, score) in responses.items():
        cursor.execute("INSERT INTO results VALUES (?, ?, ?, ?)", (candidate_name, question, response, score))
    conn.commit()
    conn.close()

# ✅ Step 7: Main Streamlit UI
def main():
    st.title("🎙️ AI-Powered Interview System")
    questions_df = load_questions()
    candidate_name = st.text_input("Enter Candidate Name")

    if candidate_name:
        responses = {}
        for idx, row in questions_df.iterrows():
            st.subheader(f"🔹 Question {idx+1}: {row['Question']}")

            # ✅ Record Answer with Error Handling
            recognizer = sr.Recognizer()
            with sr.Microphone(device_index=0) as source:  # Ensure correct mic device
                st.write("🎤 Listening... Speak now!")
                try:
                    audio = recognizer.listen(source, timeout=10)  # 10-second timeout
                    st.write("🔄 Processing...")

                    response_text = transcribe_audio(audio)
                    if response_text:
                        st.write(f"📝 Transcribed Answer: {response_text}")
                    else:
                        st.error("❌ Error processing audio or no speech detected")
                        response_text = ""
                except sr.WaitTimeoutError:
                    st.error("⏳ No response detected. Please try again.")
                    response_text = ""
                except Exception as e:
                    st.error(f"❌ Error capturing audio: {e}")
                    response_text = ""

            # ✅ Score the response
            score = score_response(response_text, row["Answer"])
            responses[row["Question"]] = (response_text, score)
            st.write(f"✅ Score: {score}/10")
            time.sleep(1)

        # ✅ Save to Database
        save_results(candidate_name, responses)

        # ✅ Show Final Report
        total_score = sum(score for _, score in responses.values())
        st.success(f"🏆 Final Score: {total_score}/{len(questions_df) * 10}")
        st.write("📜 **Interview Transcript:**")
        for question, (answer, score) in responses.items():
            st.write(f"**Q:** {question}\n**A:** {answer} (Score: {score}/10)")

if __name__ == "__main__":
    main()
