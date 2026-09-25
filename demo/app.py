"""Streamlit demo for user-research sessions.

    streamlit run demo/app.py

Enter a patient profile, pick an exercise, and play the personalized
voice-over next to the default voice so participants can compare the two.
"""

from __future__ import annotations

import streamlit as st

from voicedub.pipeline import build_services, dub, load_exercises
from voicedub.profile import SUPPORTED_LANGUAGES, VOICE_GENDERS, PatientProfile

GENDERS = {"female": "Female", "male": "Male", "other": "Other / prefer not to say"}

st.set_page_config(page_title="Personalized Voice-over", layout="wide")
st.title("Personalized Exercise Voice-over")
st.caption("Voices exercise instructions to match the patient's age, gender and app language.")

exercises = load_exercises()

with st.sidebar:
    st.header("Patient profile")
    age = st.slider("Age", 18, 95, 67)
    gender = st.radio("Gender", list(GENDERS), format_func=GENDERS.get)
    fallback = "female"
    if gender == "other":
        fallback = st.radio("Voice gender", VOICE_GENDERS, format_func=GENDERS.get)
    languages = list(SUPPORTED_LANGUAGES)
    language = st.selectbox("App language", languages, index=languages.index("en"),
                            format_func=SUPPORTED_LANGUAGES.get)

    st.header("Exercise")
    exercise_id = st.selectbox("Exercise", list(exercises), format_func=lambda i: exercises[i].title.get("en", i))
    compare = st.checkbox("Compare with default voice", value=True)

exercise = exercises[exercise_id]
bucket = PatientProfile(age, gender, language).bucket(fallback)

if language not in exercise.description:
    st.warning(f"This exercise has no {SUPPORTED_LANGUAGES[language]} description yet.")
    st.stop()

st.markdown(f"**Instruction text** · `{bucket.key}`")
st.write(exercise.description[language])

if st.button("Generate voice-over", type="primary"):
    try:
        selector, narrator = build_services()
    except Exception as e:  # missing API key etc.
        st.error(str(e))
        st.stop()

    def render(label: str, col, voice=None, suffix: str = "") -> None:
        with col, st.spinner(f"Generating {label.lower()}…"):
            # out=None: audio only, no video muxing.
            r = dub(exercise, bucket, selector=selector, narrator=narrator, out=None, voice=voice)
            st.subheader(label)
            st.caption(f"{r.voice.name} · {r.voice.source} · {r.narration_duration:.1f}s")
            audio = r.narration.read_bytes()
            st.audio(audio, format="audio/mp3")
            st.download_button(
                "Download MP3", audio, mime="audio/mpeg",
                file_name=f"{exercise.id}_{bucket.key.replace(':', '_')}{suffix}.mp3",
                key=f"download{suffix}",
            )

    cols = st.columns(2 if compare else 1)
    render("Personalized voice", cols[0])
    if compare:
        # Baseline: one fixed voice for everyone. Set "defaults" in
        # config/voice_map.json to the voice the app uses today.
        render("Default voice", cols[1], voice=selector.default("female"), suffix="_baseline")
