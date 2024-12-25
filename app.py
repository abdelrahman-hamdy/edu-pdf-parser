import streamlit as st
import pdfplumber
import openai
import json
from io import BytesIO

# Set your OpenAI API key. 
# In production, consider using Streamlit Secrets instead of hardcoding.
openai.api_key = "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"

st.title("PDF to MCQ Extractor (GPT-4)")

# File uploader
uploaded_pdf = st.file_uploader("Upload a PDF file", type=["pdf"])

# Number of MCQs to generate per chapter
num_mcqs_per_chapter = st.number_input("Number of MCQs per chapter", min_value=1, max_value=20, value=3)

if uploaded_pdf is not None:
    # Extract text from PDF
    with pdfplumber.open(uploaded_pdf) as pdf:
        pages_text = []
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text)

    combined_text = "\n".join(pages_text)

    # Display a snippet of the extracted text
    st.write("**Extracted PDF Text (preview):**")
    preview_len = 500
    if len(combined_text) > preview_len:
        st.text(combined_text[:preview_len] + "...")
    else:
        st.text(combined_text)

    if st.button("Analyze PDF & Generate MCQs"):
        with st.spinner("Analyzing with GPT-4..."):
            # 1) Identify chapters
            prompt_chapter_identification = f"""
            You are an assistant that identifies chapters and sub-chapters from the text below.
            Please return a JSON array, where each element is an object:
            {{
              "chapter_title": "string",
              "subchapters": ["string", ...]
            }}

            TEXT:
            {combined_text}
            """

            try:
                response_chapters = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt_chapter_identification}
                    ],
                    temperature=0.3
                )
                chapters_text = response_chapters.choices[0].message["content"].strip()
                st.write("**Raw chapter identification response:**")
                st.code(chapters_text, language="json")

                # Attempt to parse GPT output as JSON
                try:
                    chapters_data = json.loads(chapters_text)
                except:
                    chapters_data = [{"chapter_title": "Unlabeled Chapter", "subchapters": []}]

                # Ensure chapters_data is a list
                if not isinstance(chapters_data, list):
                    chapters_data = [chapters_data]

                # Prepare final output
                output_data = {
                    "course_name": "Unknown Course Title",
                    "chapters": []
                }

                # 2) Generate MCQs for each identified chapter
                for chapter in chapters_data:
                    chapter_title = chapter.get("chapter_title", "Untitled")
                    # subchapters = chapter.get("subchapters", [])  # Not used in this example

                    # Craft a prompt focusing on this chapter
                    prompt_mcq = f"""
                    The text below is from a course material. 
                    Focus on the topic: "{chapter_title}".
                    Please create {num_mcqs_per_chapter} multiple-choice questions relevant to this topic.
                    For each question, provide:
                      - question: the question text
                      - options: a list of 4 answer options
                      - correct_answer: which option is correct

                    Return a strictly valid JSON array, 
                    where each element is an object like:
                    {{
                      "question": "...",
                      "options": ["...", "...", "...", "..."],
                      "correct_answer": "..."
                    }}

                    TEXT:
                    {combined_text}
                    """

                    response_mcqs = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are an expert question generator."},
                            {"role": "user", "content": prompt_mcq}
                        ],
                        temperature=0.7
                    )

                    mcq_text = response_mcqs.choices[0].message["content"].strip()
                    st.write(f"**MCQ Generation for chapter:** {chapter_title}")
                    st.code(mcq_text, language="json")

                    # Parse MCQs JSON
                    try:
                        mcqs = json.loads(mcq_text)
                        # If it isn't a list, wrap it
                        if not isinstance(mcqs, list):
                            mcqs = [mcqs]
                    except:
                        mcqs = [{"question": mcq_text, "options": [], "correct_answer": ""}]

                    # Add to our output
                    chapter_entry = {
                        "chapter_title": chapter_title,
                        "mcqs": mcqs
                    }
                    output_data["chapters"].append(chapter_entry)

                # Show final JSON in the Streamlit UI
                st.subheader("Final JSON Structure")
                st.json(output_data)

                # Provide download button
                json_str = json.dumps(output_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name="mcq_output.json",
                    mime="application/json"
                )

            except Exception as e:
                st.error(f"Error calling OpenAI API: {e}")