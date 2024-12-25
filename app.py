import streamlit as st
import pdfplumber
from openai import OpenAI

client = OpenAI(st.secrets["OPENAI_API_KEY"])
import json
from io import BytesIO

st.title("PDF to MCQ Extractor (GPT-4)")

uploaded_pdf = st.file_uploader("Upload a PDF file", type=["pdf"])
num_mcqs_per_chapter = st.number_input("Number of MCQs per chapter", min_value=1, max_value=20, value=3)

if uploaded_pdf is not None:
    with pdfplumber.open(uploaded_pdf) as pdf:
        # Extract text from all pages
        all_text = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)
    combined_text = "\n".join(all_text)

    st.write("**Extracted PDF Text (Preview)**")
    st.text(combined_text[:500] + "..." if len(combined_text) > 500 else combined_text)

    if st.button("Generate MCQs with GPT-4"):
        with st.spinner("Analyzing PDF with GPT-4..."):

            # STEP 1: Identify chapters
            prompt_chapters = f"""
            You are a helpful assistant. 
            Identify major chapters or sections from the text below, 
            then return them as a JSON array. 
            Example:
              [
                {{ "chapter_title": "Introduction", "subchapters": [] }},
                {{ "chapter_title": "Main Content", "subchapters": ["Part A","Part B"] }}
              ]

            TEXT:
            {combined_text}
            """

            try:
                chapter_resp = client.chat.completions.create(model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt_chapters}
                ],
                temperature=0.0)
                chapters_str = chapter_resp.choices[0].message.content.strip()
                st.write("**GPT-4 Raw Chapters Output:**")
                st.code(chapters_str, language="json")

                try:
                    chapters_data = json.loads(chapters_str)
                except:
                    # Fallback if GPT output isn't valid JSON
                    chapters_data = [{"chapter_title": "Unknown Chapter", "subchapters": []}]

                if not isinstance(chapters_data, list):
                    chapters_data = [chapters_data]

                # Prepare final output structure
                output_data = {
                    "course_name": "Untitled Course",
                    "chapters": []
                }

                # STEP 2: Generate MCQs for each chapter
                for chapter_info in chapters_data:
                    chapter_title = chapter_info.get("chapter_title", "Untitled")

                    prompt_mcqs = f"""
                    Focus on the topic: "{chapter_title}".
                    Please create {num_mcqs_per_chapter} multiple choice questions 
                    about this topic. 
                    Each question must have:
                      - 'question' (string)
                      - 'options' (4 distinct strings in a list)
                      - 'correct_answer' (one of the options)

                    Return ONLY valid JSON, e.g.:
                    [
                      {{
                        "question": "...",
                        "options": ["A", "B", "C", "D"],
                        "correct_answer": "A"
                      }}
                    ]

                    TEXT:
                    {combined_text}
                    """

                    mcq_resp = client.chat.completions.create(model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert question generator."},
                        {"role": "user", "content": prompt_mcqs}
                    ],
                    temperature=0.7)
                    mcq_output_str = mcq_resp.choices[0].message.content.strip()
                    st.write(f"**GPT-4 Raw MCQs for Chapter:** {chapter_title}")
                    st.code(mcq_output_str, language="json")

                    # Parse MCQ JSON
                    try:
                        mcqs = json.loads(mcq_output_str)
                        if not isinstance(mcqs, list):
                            mcqs = [mcqs]
                    except:
                        mcqs = [{"question": mcq_output_str, "options": [], "correct_answer": ""}]

                    # Append to final structure
                    output_data["chapters"].append({
                        "chapter_title": chapter_title,
                        "mcqs": mcqs
                    })

                # Display final JSON
                st.subheader("Final Output Data")
                st.json(output_data)

                # Download button
                json_string = json.dumps(output_data, indent=2)
                st.download_button(
                    label="Download as JSON",
                    data=json_string,
                    file_name="mcqs_output.json",
                    mime="application/json"
                )

            except Exception as e:
                st.error(f"Error calling OpenAI API: {e}")