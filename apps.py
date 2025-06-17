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

st.set_page_config(page_title="AI Homework Helper", layout="wide")

# Initialize OpenAI client
client = openai.OpenAI(api_key="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", base_url="https://openrouter.ai/api/v1")

# Subject prompts
subject_prompts = {
    "General": "You are a helpful AI tutor for school students.",
    "Math": "You are a helpful math tutor for school students.",
    "Science": "You are a science teacher helping students understand key concepts.",
    "History": "You are a history teacher explaining historical facts.",
}

# Supported languages
language_options = {
    "Hindi": "hi", "Telugu": "te", "Tamil": "ta", "Bengali": "bn",
    "Gujarati": "gu", "Marathi": "mr", "Kannada": "kn", "Urdu": "ur",
    "English": "en", "French": "fr", "Spanish": "es", "German": "de",
    "Chinese": "zh-CN", "Japanese": "ja", "Russian": "ru",
}

# Initialize session state
for key in ["messages", "latest_answer", "translated_text", "last_translation_lang", "quiz_score", "quiz_index"]:
    if key not in st.session_state:
        st.session_state[key] = None if key not in ["messages", "quiz_score", "quiz_index"] else ([] if key == "messages" else 0)

# Helper functions
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
    with open(filename, "w") as f:
        for msg in messages:
            f.write(f"{msg['role']}: {msg['content']}\n")
    return filename

def save_to_pdf(messages):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for msg in messages:
        pdf.multi_cell(0, 10, f"{msg['role']}: {msg['content']}")
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
            st.error("Sorry, could not understand audio.")
        except sr.RequestError:
            st.error("Speech recognition service failed.")
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
            options = [lines[1][3:].strip(), lines[2][3:].strip(), lines[3][3:].strip(), lines[4][3:].strip()]
            answer_line = lines[5]
            answer_letter = answer_line.split(":")[-1].strip()
            answer_map = {"A": options[0], "B": options[1], "C": options[2], "D": options[3]}
            correct_answer = answer_map.get(answer_letter.upper(), "")
            questions.append({
                "question": question,
                "options": options,
                "answer": correct_answer
            })
    return questions

# App UI
st.title("📚 AI Homework Helper")

# Ask Question Tab
st.markdown("---")
st.subheader("💬 Ask Your Question")
subject = st.selectbox("📘 Subject", list(subject_prompts.keys()))
prompt = st.text_input("Type your question here...")

# Button: ONLY ONCE
if st.button("🔍 Get Answer", key="get_answer") and prompt:
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

# Only show translate and download after an answer is generated
if st.session_state.latest_answer:
    # Translate Section
    st.subheader("🌐 Translate the Answer")
    lang = st.selectbox("Choose Language", list(language_options.keys()), key="lang_select")
    if st.button("🌍 Translate", key="translate"):
        translated = translate_text(st.session_state.latest_answer, language_options[lang])
        st.session_state.translated_text = translated
        st.session_state.last_translation_lang = lang
        st.success(f"Translated to {lang}")
        st.write(translated)
        audio = text_to_speech(translated, language_options[lang])
        st.audio(audio, format="audio/mp3")
        os.unlink(audio)

    # Download Section
    st.subheader("⬇️ Download Conversation")
    if st.button("📄 TXT", key="txt"):
        fname = save_to_txt(st.session_state.messages)
        with open(fname, "rb") as f:
            st.download_button("Download TXT", f, file_name=fname)
    if st.button("📑 PDF", key="pdf"):
        fname = save_to_pdf(st.session_state.messages)
        with open(fname, "rb") as f:
            st.download_button("Download PDF", f, file_name=fname)


# Real-Time Quiz Section
st.markdown("---")
st.subheader("🧪 Real-Time Quiz Generator")
quiz_topic = st.text_input("📌 Enter a topic for quiz generation")

if st.button("🧪 Generate Quiz") and quiz_topic:
    quiz_prompt = (
        f"Generate a 5-question multiple-choice quiz on the topic '{quiz_topic}'. "
        "Each question should include 4 options labeled A, B, C, D and the correct answer at the end "
        "in the format: 'Answer: <Correct Option Letter>'.\n\n"
        "Format strictly like this:\n"
        "Q1. What is ...?\nA) Option1\nB) Option2\nC) Option3\nD) Option4\nAnswer: B\n\n"
        "Q2. ...\n..."
    )
    response = get_gpt_response(quiz_prompt, "General")
    st.session_state.quiz_data = parse_quiz_data(response)
    st.session_state.quiz_score = 0
    st.session_state.quiz_index = 0

if "quiz_data" in st.session_state and st.session_state.quiz_data:
    total_questions = len(st.session_state.quiz_data)
    current_index = st.session_state.quiz_index

    if current_index < total_questions:
        q_obj = st.session_state.quiz_data[current_index]
        st.markdown(f"**Question {current_index + 1} of {total_questions}**")
        st.write(q_obj["question"])

        if "answer_submitted" not in st.session_state:
            st.session_state.answer_submitted = False
            st.session_state.answer_correct = False

        if not st.session_state.answer_submitted:
            with st.form(key=f"quiz_form_{current_index}"):
                selected = st.radio("Choose your answer:", q_obj["options"], key=f"option_{current_index}")
                submitted = st.form_submit_button("Submit Answer")

                if submitted:
                    is_correct = selected.strip().lower() == q_obj["answer"].strip().lower()
                    st.session_state.answer_submitted = True
                    st.session_state.answer_correct = is_correct
                    if is_correct:
                        st.session_state.quiz_score += 1

        else:
            if st.session_state.answer_correct:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect! The correct answer is: {q_obj['answer']}")

            if st.button("Next Question"):
                st.session_state.quiz_index += 1
                st.session_state.answer_submitted = False  # reset for next question
                st.session_state.answer_correct = False

    else:
        st.success(f"🎉 Quiz Completed! Your final score is **{st.session_state.quiz_score}/{total_questions}**")
        if st.button("Restart Quiz"):
            st.session_state.quiz_index = 0
            st.session_state.quiz_score = 0
            st.session_state.answer_submitted = False
            st.session_state.answer_correct = False


# Manual note input
st.markdown("---")
st.subheader("📝 Paste Your Notes")
text = st.text_area("Paste text to summarize or generate content")

# Summarize Section
st.markdown("---")
st.subheader("📌 Summarize Notes")
if st.button("📚 Summarize Notes") and text:
    summary_prompt = f"Summarize this text with bullet points and create 3 flashcards:\n{text}"
    response = get_gpt_response(summary_prompt, "General")
    st.markdown("### 📌 Summary")
    st.write(response)

# Generate Topic Section
st.markdown("---")
st.subheader("🧠 Generate Topic Content")
if st.button("🧠 Generate Topic Content") and text:
    topic_prompt = f"Generate short notes, 5 practice questions, and definitions on the topic: {text}"
    response = get_gpt_response(topic_prompt, "General")
    st.markdown("### 📝 Topic Content")
    st.write(response)



# Sidebar: Usage Stats
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Usage Stats")
st.sidebar.metric("Questions Asked", len([m for m in st.session_state.messages if m['role']=='user']))
st.sidebar.metric("Answers Generated", len([m for m in st.session_state.messages if m['role']=='assistant']))
