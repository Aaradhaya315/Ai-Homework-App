import streamlit as st
import openai
from gtts import gTTS
import tempfile
import os
from deep_translator import GoogleTranslator
import datetime
from fpdf import FPDF
import speech_recognition as sr
import re

# --- Streamlit Configuration ---
st.set_page_config(page_title="AI Homework Helper", layout="wide")

# API Key Setup
api_key = st.secrets["OPENAI_API_KEY"] if "OPENAI_API_KEY" in st.secrets else ""
openai.api_key = api_key
client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

# Subject Prompts
subject_prompts = {
    "General": "You are a helpful AI tutor for school students.",
    "Math": "You are a helpful math tutor for school students.",
    "Science": "You are a science teacher helping students understand key concepts.",
    "History": "You are a history teacher explaining historical facts.",
}

# Languages
language_options = {
    "Hindi": "hi", "Telugu": "te", "Tamil": "ta", "Bengali": "bn",
    "Gujarati": "gu", "Marathi": "mr", "Kannada": "kn", "Urdu": "ur",
    "English": "en", "French": "fr", "Spanish": "es", "German": "de",
    "Chinese": "zh-CN", "Japanese": "ja", "Russian": "ru",
}

# Initialize state
for key in ["messages", "latest_answer", "translated_text", "last_translation_lang", "quiz_score", "quiz_index", "quiz_data", "answer_submitted", "answer_correct"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "messages" or key == "quiz_data" else 0 if key in ["quiz_score", "quiz_index"] else False if key in ["answer_submitted", "answer_correct"] else None

# --- Helper Functions ---
def get_gpt_response(prompt, subject):
    system_prompt = subject_prompts.get(subject, subject_prompts["General"])
    messages = [{"role": "system", "content": system_prompt}] + st.session_state.messages
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages + [{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def text_to_speech(text, lang='en'):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts = gTTS(text=text, lang=lang)
        tts.save(fp.name)
        return fp.name

def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        st.error(f"Translation error: {e}")
        return ""

def save_to_txt(messages):
    filename = f"conversation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(f"{msg['role']}: {msg['content']}\n")
    return filename

def save_to_pdf(messages):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for msg in messages:
        safe_text = msg["content"].encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 10, f"{msg['role']}: {safe_text}")
    filename = f"conversation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    return filename

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Please speak your question.")
        audio = recognizer.listen(source)
        try:
            query = recognizer.recognize_google(audio)
            st.success(f"You said: {query}")
            return query
        except sr.UnknownValueError:
            st.error("Could not understand audio.")
        except sr.RequestError:
            st.error("Speech recognition failed.")
    return ""

def parse_quiz_data(response_text):
    question_blocks = re.findall(
        r"(Q\d+\. .*?(?:\nA\).*?\nB\).*?\nC\).*?\nD\).*?\nAnswer:.*?))(?=\nQ\d+\.|\Z)",
        response_text, re.DOTALL
    )
    questions = []
    for block in question_blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 6:
            question = lines[0]
            options = [lines[1][3:], lines[2][3:], lines[3][3:], lines[4][3:]]
            answer_letter = lines[5].split(":")[-1].strip().upper()
            correct_answer = options[ord(answer_letter) - ord("A")] if answer_letter in "ABCD" else ""
            questions.append({"question": question, "options": options, "answer": correct_answer})
    return questions

# --- Main UI ---
st.title("📚 AI Homework Helper")
st.subheader("💬 Ask Your Question")

subject = st.selectbox("📘 Subject", list(subject_prompts.keys()), key="subject")
prompt = st.text_input("Type your question here...", key="question_input")

if st.button("🔍 Get Answer", key="get_answer_btn") and prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Thinking..."):
        response = get_gpt_response(prompt, subject)
        st.session_state.latest_answer = response
        st.session_state.translated_text = ""
        st.session_state.last_translation_lang = ""
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.success("Answer Generated!")
        st.write(response)
        audio = text_to_speech(response)
        st.audio(audio, format="audio/mp3")
        os.unlink(audio)

# --- Translation ---
if st.session_state.latest_answer:
    st.subheader("🌐 Translate the Answer")
    lang = st.selectbox("Choose Language", list(language_options.keys()), key="lang_selector")
    if st.button("🌍 Translate", key="translate_btn"):
        translated = translate_text(st.session_state.latest_answer, language_options[lang])
        st.session_state.translated_text = translated
        st.session_state.last_translation_lang = lang
        st.success(f"Translated to {lang}")
        st.write(translated)
        audio = text_to_speech(translated, language_options[lang])
        st.audio(audio, format="audio/mp3")
        os.unlink(audio)

# --- Download Section ---
if st.session_state.latest_answer:
    st.subheader("⬇️ Download Conversation")
    if st.button("📄 TXT"):
        fname = save_to_txt(st.session_state.messages)
        with open(fname, "rb") as f:
            st.download_button("Download TXT", f, file_name=fname)
    if st.button("📁 PDF"):
        fname = save_to_pdf(st.session_state.messages)
        with open(fname, "rb") as f:
            st.download_button("Download PDF", f, file_name=fname)

# --- Quiz Section ---
st.markdown("---")
st.subheader("🧠 Real-Time Quiz Generator")
quiz_topic = st.text_input("📌 Enter a topic for quiz generation", key="quiz_topic")

if st.button("🧠 Generate Quiz", key="generate_quiz") and quiz_topic:
    quiz_prompt = (
        f"Create a 5-question multiple-choice quiz on '{quiz_topic}'. "
        "Each question should be formatted as follows:\n\n"
        "Q1. What is ...?\n"
        "A) Option A\n"
        "B) Option B\n"
        "C) Option C\n"
        "D) Option D\n"
        "Answer: B\n\n"
        "Ensure all 5 questions follow this exact format."
    )

    response = get_gpt_response(quiz_prompt, "General")
    st.write("🔍 GPT Raw Quiz Response:")
    st.code(response)
    st.session_state.quiz_data = parse_quiz_data(response)
    st.session_state.quiz_score = 0
    st.session_state.quiz_index = 0
    st.session_state.answer_submitted = False
    st.rerun()

# --- Display Quiz Only If Data Exists ---
if st.session_state.quiz_data:
    total = len(st.session_state.quiz_data)
    index = st.session_state.quiz_index

    if index < total:
        q_obj = st.session_state.quiz_data[index]
        st.markdown(f"**Question {index + 1} of {total}**")
        st.write(q_obj["question"])

        with st.form(key=f"quiz_form_{index}"):
            selected = st.radio("Choose your answer:", q_obj["options"], key=f"option_{index}")
            submitted = st.form_submit_button("Submit Answer")
            if submitted:
                is_correct = selected.strip().lower() == q_obj["answer"].strip().lower()
                st.session_state.answer_submitted = True
                st.session_state.answer_correct = is_correct
                if is_correct:
                    st.session_state.quiz_score += 1
                st.rerun()

        if st.session_state.answer_submitted:
            if st.session_state.answer_correct:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect! The correct answer is: {q_obj['answer']}")
            if st.button("Next Question", key=f"next_{index}"):
                st.session_state.quiz_index += 1
                st.session_state.answer_submitted = False
                st.rerun()

    elif index >= total:
        st.success(f"🎉 Quiz Completed! Final Score: {st.session_state.quiz_score}/{total}")
        if st.button("Restart Quiz"):
            st.session_state.quiz_index = 0
            st.session_state.quiz_score = 0
            st.session_state.answer_submitted = False
            st.session_state.quiz_data = []
            st.rerun()


# --- Notes Section ---
st.markdown("---")
st.subheader("📝 Paste Your Notes")
text = st.text_area("Paste text to summarize or generate content", key="notes_text")

st.subheader("📚 Summarize Notes")
if st.button("Summarize Notes", key="summarize_notes") and text:
    summary_prompt = f"Summarize this text with bullet points and create 3 flashcards:\n{text}"
    response = get_gpt_response(summary_prompt, "General")
    st.markdown("### 📂 Summary")
    st.write(response)

st.subheader("🧠 Generate Topic Content")
if st.button("Generate Topic Content", key="generate_topic") and text:
    topic_prompt = f"Generate short notes, 5 practice questions, and definitions on the topic: {text}"
    response = get_gpt_response(topic_prompt, "General")
    st.markdown("### 📝 Topic Content")
    st.write(response)

# --- Sidebar Metrics ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Usage Stats")
st.sidebar.metric("Questions Asked", len([m for m in st.session_state.messages if m['role'] == 'user']))
st.sidebar.metric("Answers Generated", len([m for m in st.session_state.messages if m['role'] == 'assistant']))


