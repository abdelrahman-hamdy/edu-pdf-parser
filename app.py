import streamlit as st
import openai
import pdfplumber
import json
from io import BytesIO

# ========================================
# 1. SET YOUR OPENAI API KEY
# ========================================
openai.api_key = "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"

# ========================================
# 2. STREAMLIT UI
# ========================================
st.title("PDF to MCQ Extractor")

uploaded_pdf = st.file_uploader("Upload a PDF file", type=["pdf"])

# Optional: Let the user specify how many MCQs to generate per chapter
num_mcqs_per_chapter = st.number_input("Number of MCQs per chapter", min_value=1, max_value=20, value=3)

if uploaded_pdf is not None:
    # ========================================
    # 3. EXTRACT TEXT (AND IMAGES) FROM PDF
    # ========================================
    with pdfplumber.open(uploaded_pdf) as pdf:
        full_text = []
        for page_idx, page in enumerate(pdf.pages):
            # Extract text
            page_text = page.extract_text()
            
            if page_text:
                # Store text with page index (in case you need to track image positions)
                full_text.append({"page_index": page_idx, "text": page_text})
            
            # If you need images:
            # images = page.images
            # for img in images:
            #     # pdfplumber provides bounding box, image data, etc.
            #     # You can extract and store them if needed.
            #     pass

    # Combine text into a single string or handle it page-by-page
    # For simplicity, let's just combine everything
    combined_text = "\n".join([p["text"] for p in full_text if p["text"]])

    # Display the first few hundred characters of the extracted text
    st.write("**Extracted PDF Text (preview):**")
    st.text(combined_text[:500] + "..." if len(combined_text) > 500 else combined_text)

    # ========================================
    # 4. RECOGNIZE CHAPTERS & GENERATE MCQS
    # ========================================
    # We'll do this in two steps: 
    #   (A) Identify chapters
    #   (B) Generate MCQs for each chapter
    # You could do it in one shot with a more elaborate prompt, but let's keep it modular.

    if st.button("Process PDF and Generate MCQs"):
        with st.spinner("Analyzing the PDF with OpenAI..."):

            # --- (A) Identify chapters via prompt
            prompt_chapter_identification = f"""
            You are an assistant that identifies chapters and sub-chapters from text. 
            Given the text below, please outline the chapters and sub-chapters 
            in a simple JSON array, with each element representing a chapter. 
            Each element should have a "chapter_title" and (optional) "subchapters".

            TEXT:
            {combined_text}
            """

            try:
                response_chapters = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt_chapter_identification}
                    ],
                    temperature=0.3
                )
                chapters_text = response_chapters.choices[0].message["content"]
                st.write("**Raw chapter identification response:**")
                st.code(chapters_text, language="json")

                # Attempt to parse it as JSON. GPT output can be inconsistent;
                # you might want to use a safer parser or add instructions in the prompt
                # for strict JSON format.
                try:
                    chapters_data = json.loads(chapters_text)
                except:
                    # If JSON parse fails, wrap it in a fallback structure
                    chapters_data = [{"chapter_title": "Unlabeled Chapter", "subchapters": []}]

                # If chapters_data is not a list, ensure it is
                if not isinstance(chapters_data, list):
                    chapters_data = [chapters_data]

                # --- (B) Generate MCQs for each chapter
                # We'll create an overall data structure:
                output_data = {
                    "course_name": "Unknown Course Title",
                    "chapters": []
                }

                for chapter in chapters_data:
                    chapter_title = chapter.get("chapter_title", "Untitled")
                    subchapters = chapter.get("subchapters", [])

                    # You could refine the text that belongs to this chapter
                    # using a more advanced approach if you know the page ranges,
                    # but for simplicity, let's just feed the entire combined text
                    # again to generate MCQs relevant to that chapter.

                    prompt_mcq = f"""
                    The following content is part of a course material. 
                    Focus on the topic: "{chapter_title}".
                    Please create {num_mcqs_per_chapter} multiple choice questions 
                    that are relevant to this topic. 
                    Each question should have 4 answer options with exactly one correct answer. 
                    Provide the correct answer explicitly.

                    Overall text:
                    {combined_text}
                    """

                    response_mcqs = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are an expert question generator."},
                            {"role": "user", "content": prompt_mcq}
                        ],
                        temperature=0.7
                    )

                    mcq_text = response_mcqs.choices[0].message["content"]
                    st.write(f"**MCQ Generation for chapter:** {chapter_title}")
                    st.code(mcq_text, language="json")

                    # Attempt to parse into a structure
                    # Because GPT might not strictly produce JSON, you might have to
                    # parse it carefully. We'll assume well-formed JSON for this example.
                    # If the LLM responds in a normal text format, you'd parse or do regex.

                    try:
                        mcqs = json.loads(mcq_text)
                        # If the result is not a list, we wrap it
                        if not isinstance(mcqs, list):
                            mcqs = [mcqs]
                    except:
                        # fallback
                        mcqs = [{"question": mcq_text, "options": [], "correct_answer": ""}]

                    # Construct the chapter entry
                    chapter_entry = {
                        "chapter_title": chapter_title,
                        "mcqs": mcqs
                    }
                    output_data["chapters"].append(chapter_entry)

                # ========================================
                # 5. DISPLAY OR RETURN FINAL JSON
                # ========================================
                st.subheader("Final JSON Structure")
                st.json(output_data)

            except Exception as e:
                st.error(f"Error calling OpenAI API: {e}")