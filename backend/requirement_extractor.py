
import json
import re

from llm_service import generate_response


VALID_CATEGORIES = {
    "FUNCTIONAL",
    "BUSINESS_RULE",
    "NON_FUNCTIONAL",
    "CONSTRAINT",
    "ASSUMPTION",
    "OPEN_QUESTION"
}

MAX_CHUNK_CHARS = 4500


# ---------------------------------------------------------
# 1. Split the document into smaller chunks
# ---------------------------------------------------------

def split_document_into_chunks(document_text: str) -> list[str]:
    """
    Split document text into smaller chunks while keeping
    paragraphs together whenever possible.
    """

    paragraphs = [
        paragraph.strip()
        for paragraph in document_text.splitlines()
        if paragraph.strip()
    ]

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:

        if len(paragraph) > MAX_CHUNK_CHARS:

            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            for start in range(0, len(paragraph), MAX_CHUNK_CHARS):
                chunks.append(
                    paragraph[start:start + MAX_CHUNK_CHARS]
                )

            continue

        if len(current_chunk) + len(paragraph) + 1 <= MAX_CHUNK_CHARS:

            current_chunk += (
                "\n" + paragraph if current_chunk else paragraph
            )

        else:
            chunks.append(current_chunk)
            current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# ---------------------------------------------------------
# 2. Parse the JSON response from Ollama
# ---------------------------------------------------------

def parse_json_response(response_text: str) -> dict:
    """
    Extract a JSON object from the model response.
    """

    cleaned_response = response_text.strip()

    cleaned_response = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned_response,
        flags=re.IGNORECASE
    )

    cleaned_response = re.sub(
        r"\s*```$",
        "",
        cleaned_response
    )

    start = cleaned_response.find("{")
    end = cleaned_response.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    return json.loads(cleaned_response[start:end + 1])


# ---------------------------------------------------------
# 3. Validate an individual requirement
# ---------------------------------------------------------

def validate_requirement(requirement: dict) -> bool:

    if not isinstance(requirement, dict):
        return False

    category = requirement.get("category")
    description = requirement.get("description")
    source = requirement.get("source")

    if category not in VALID_CATEGORIES:
        return False

    if not isinstance(description, str) or not description.strip():
        return False

    if not isinstance(source, str) or not source.strip():
        return False

    return True


# ---------------------------------------------------------
# 4. Extract requirements from one document chunk
# ---------------------------------------------------------

def extract_from_chunk(
    chunk: str,
    chunk_number: int
) -> list[dict]:

    prompt = f"""
You are a professional business and software requirements analyst.

Extract all distinct requirements from the document section below.

SECTION NUMBER: {chunk_number}

DOCUMENT SECTION:
{chunk}

Use exactly one of these categories:

FUNCTIONAL:
A capability or behaviour the system must provide.

BUSINESS_RULE:
A business policy, calculation rule, threshold or decision rule.

NON_FUNCTIONAL:
A quality requirement such as performance, security,
reliability, usability or auditability.

CONSTRAINT:
A technical, regulatory, operational or implementation restriction.

ASSUMPTION:
Something believed to be true but not yet confirmed.

OPEN_QUESTION:
Something requiring clarification or a decision.

IMPORTANT INSTRUCTIONS:

1. Preserve exact amounts, numbers, percentages, thresholds,
   conditions and exceptions.

2. Distinguish existing behaviour from newly requested behaviour.

3. Do not invent requirements or missing information.

4. Do not convert assumptions or open questions into confirmed
   requirements.

5. Extract each distinct requirement separately.

6. Do not combine multiple independent requirements into one
   general statement.

7. Do not repeat the same requirement using different wording.

8. Include a source reference identifying the relevant heading,
   paragraph, page or section.

9. If an exact source heading is unavailable, use section
   number {chunk_number}.

10. Do not generate requirement IDs.

Return ONLY valid JSON:

{{
  "requirements": [
    {{
      "category": "FUNCTIONAL",
      "description": "Requirement description.",
      "source": "Relevant source reference."
    }}
  ]
}}

If no requirements are found, return:

{{
  "requirements": []
}}
"""

    response = generate_response(prompt)
    parsed = parse_json_response(response)

    requirements = parsed.get("requirements")

    if not isinstance(requirements, list):
        raise ValueError(
            f"Invalid requirements list in section {chunk_number}."
        )

    valid_requirements = []

    for requirement in requirements:

        if validate_requirement(requirement):

            valid_requirements.append({
                "category": requirement["category"],
                "description": requirement["description"].strip(),
                "source": requirement["source"].strip()
            })

    return valid_requirements


# ---------------------------------------------------------
# 5. Remove exact duplicates safely
# ---------------------------------------------------------

def remove_exact_duplicates(
    requirements: list[dict]
) -> list[dict]:
    """
    Remove only exact textual duplicates within the same category.

    Similar but differently worded requirements are preserved.
    This avoids accidentally deleting distinct requirements.
    """

    unique_requirements = []
    seen = set()

    for requirement in requirements:

        normalized_description = re.sub(
            r"\s+",
            " ",
            requirement["description"].strip().lower()
        )

        duplicate_key = (
            requirement["category"],
            normalized_description
        )

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)
        unique_requirements.append(requirement)

    return unique_requirements


# ---------------------------------------------------------
# 6. Consolidate semantic duplicates
# ---------------------------------------------------------

def consolidate_requirements(
    candidate_requirements: list[dict]
) -> list[dict]:
    """
    Ask the LLM to merge genuine semantic duplicates.

    If the model removes too many requirements, retain the
    original candidates after exact duplicate removal.
    """

    if not candidate_requirements:
        return []

    prompt = f"""
You are a senior business analyst.

Review the candidate requirements below and remove only genuine
semantic duplicates.

CANDIDATE REQUIREMENTS:

{json.dumps(candidate_requirements, indent=2, ensure_ascii=False)}

RULES:

1. Two requirements are duplicates only when they describe
   substantially the same underlying behaviour or business rule.

2. Do not merge different behaviours, conditions, calculations,
   constraints, assumptions or open questions.

3. Preserve every distinct requirement.

4. Preserve exact numbers, amounts, thresholds and conditions.

5. Preserve the original category unless it is clearly incorrect.

6. Never combine unrelated requirements into one general statement.

7. Preserve source references. Combine source references only
   when genuinely duplicate requirements are merged.

8. Do not invent missing information.

9. Do not create requirement IDs.

10. The final result must retain all distinct candidate requirements.
    Do not aggressively reduce the number of requirements.

Return ONLY valid JSON:

{{
  "requirements": [
    {{
      "category": "BUSINESS_RULE",
      "description": "Requirement description.",
      "source": "Source reference."
    }}
  ]
}}
"""

    response = generate_response(prompt)
    parsed = parse_json_response(response)

    consolidated = parsed.get("requirements")

    if not isinstance(consolidated, list):
        raise ValueError("Invalid consolidated requirements list.")

    valid_consolidated = []

    for requirement in consolidated:

        if validate_requirement(requirement):

            valid_consolidated.append({
                "category": requirement["category"],
                "description": requirement["description"].strip(),
                "source": requirement["source"].strip()
            })

    # Safety check: prevent excessive loss of requirements.
    minimum_expected = max(
        2,
        int(len(candidate_requirements) * 0.40)
    )

    if len(valid_consolidated) < minimum_expected:

        print(
            "\nWARNING: Consolidation removed too many requirements."
        )

        print(
            "Keeping candidate requirements instead of using "
            "the unreliable consolidated result."
        )

        return remove_exact_duplicates(candidate_requirements)

    return remove_exact_duplicates(valid_consolidated)


# ---------------------------------------------------------
# 7. Assign final sequential requirement IDs
# ---------------------------------------------------------

def assign_requirement_ids(
    requirements: list[dict]
) -> list[dict]:

    final_requirements = []

    for index, requirement in enumerate(requirements, start=1):

        final_requirements.append({
            "requirement_id": f"REQ-{index:03d}",
            "category": requirement["category"],
            "description": requirement["description"],
            "source": requirement["source"]
        })

    return final_requirements


# ---------------------------------------------------------
# 8. Main extraction function
# ---------------------------------------------------------

def extract_requirements(document_text: str) -> list[dict]:
    """
    Extract structured requirements from an uploaded document.

    Processing stages:
    1. Validate document text.
    2. Split document into smaller chunks.
    3. Extract requirements from each chunk.
    4. Consolidate semantic duplicates.
    5. Assign sequential requirement IDs.

    The function signature remains compatible with
    analysis_pipeline.py.
    """

    if not isinstance(document_text, str) or not document_text.strip():
        raise ValueError("Document text cannot be empty.")

    print("\nStarting requirement extraction...")

    # Step 1: Split document.
    chunks = split_document_into_chunks(document_text)

    print(f"Document divided into {len(chunks)} sections.")

    # Step 2: Extract requirements from each chunk.
    candidate_requirements = []

    for index, chunk in enumerate(chunks, start=1):

        print(
            f"\nProcessing section {index}/{len(chunks)}..."
        )

        extracted = extract_from_chunk(chunk, index)

        candidate_requirements.extend(extracted)

        print(
            f"Extracted {len(extracted)} requirements."
        )

    print(
        f"\nTotal candidate requirements: "
        f"{len(candidate_requirements)}"
    )

    # Step 3: Consolidate duplicates.
    print("\nConsolidating requirements...")

    consolidated = consolidate_requirements(
        candidate_requirements
    )

    print(
        f"Requirements after consolidation: {len(consolidated)}"
    )

    # Step 4: Assign IDs.
    final_requirements = assign_requirement_ids(
        consolidated
    )

    # Step 5: Display category counts.
    category_counts = {}

    for requirement in final_requirements:

        category = requirement["category"]

        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

    print("\nRequirement extraction completed.")

    print(
        f"Final requirements: {len(final_requirements)}"
    )

    print("\nCategory distribution:")

    for category, count in category_counts.items():
        print(f"  {category}: {count}")

    return final_requirements
