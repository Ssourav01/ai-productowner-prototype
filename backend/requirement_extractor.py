
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


def _parse_response(response_text: str) -> dict:
    """Parse the JSON returned by the local language model."""

    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError("The AI returned an empty response.")

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        response_text.strip(),
        flags=re.IGNORECASE
    )

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"The AI returned invalid JSON: {error}"
        ) from error

    if not isinstance(result, dict):
        raise ValueError("AI response must be a JSON object.")

    if not isinstance(result.get("requirements"), list):
        raise ValueError(
            "AI response does not contain a requirements list."
        )

    return result


def _validate_requirements(requirements: list[dict]) -> list[dict]:
    """Validate extracted requirements and their identifiers."""

    if not requirements:
        raise ValueError(
            "No requirements were extracted from the document."
        )

    seen_ids = set()
    validated_requirements = []

    for index, requirement in enumerate(requirements, start=1):

        if not isinstance(requirement, dict):
            raise ValueError("Invalid requirement format.")

        required_fields = [
            "requirement_id",
            "category",
            "description",
            "source"
        ]

        for field in required_fields:
            if field not in requirement:
                raise ValueError(
                    f"Requirement is missing the '{field}' field."
                )

        requirement_id = requirement["requirement_id"]

        if not isinstance(requirement_id, str):
            raise ValueError("Invalid requirement ID.")

        expected_id = f"REQ-{index:03d}"

        if requirement_id != expected_id:
            raise ValueError(
                f"Expected {expected_id}, received {requirement_id}."
            )

        if requirement_id in seen_ids:
            raise ValueError(
                f"Duplicate requirement ID: {requirement_id}"
            )

        seen_ids.add(requirement_id)

        category = requirement["category"]

        if not isinstance(category, str) or category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid requirement category: {category}"
            )

        for field in ["description", "source"]:

            if (
                not isinstance(requirement[field], str)
                or not requirement[field].strip()
            ):
                raise ValueError(
                    f"Requirement has an invalid '{field}' field."
                )

        validated_requirements.append(requirement)

    return validated_requirements


def extract_requirements(document_text: str) -> list[dict]:
    """
    Extract structured, non-duplicated requirements from an
    uploaded business change-request document using Ollama.
    """

    # ---------------------------------------------------------
    # 1. Validate document text
    # ---------------------------------------------------------

    if not isinstance(document_text, str) or not document_text.strip():
        raise ValueError("Document text cannot be empty.")

    # ---------------------------------------------------------
    # 2. Prepare extraction prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an experienced Business Analyst specializing in
software requirements engineering.

Analyse the complete business change-request document.

Extract all distinct and relevant requirements accurately.
Preserve important information without creating duplicates.

REQUIREMENT CATEGORIES:

1. FUNCTIONAL:
A specific capability or behaviour the system must provide.

2. BUSINESS_RULE:
A business policy, calculation, threshold, limit or decision rule.

3. NON_FUNCTIONAL:
A quality requirement such as performance, security,
availability, reliability or usability.

4. CONSTRAINT:
A restriction or condition limiting the solution.

5. ASSUMPTION:
An explicitly stated or necessary but unconfirmed assumption.

6. OPEN_QUESTION:
An unresolved decision or question requiring clarification.

IMPORTANT EXTRACTION RULES:

A. SEMANTIC DEDUPLICATION

This is extremely important.

- Do not create multiple requirements describing the same behaviour.
- Compare meaning, not just wording.
- Do not repeat a business rule as a separate functional
  requirement when both describe exactly the same behaviour.
- Do not repeat the same numerical mapping in multiple entries.
- If several document sections describe the same rule,
  create one requirement and preserve the relevant source sections.
- Keep genuinely different conditions as separate requirements.
- Do not merge unrelated requirements just to reduce the count.

Examples of duplication to avoid:

- "Apply the correct limit based on account package."
- "Determine the daily limit using the customer's package."

If both describe the same behaviour, extract one requirement.

B. PRESERVE BUSINESS VALUES

Preserve every explicit mapping exactly.

For example:

- Basic -> EUR 1,000 per day
- Premium -> EUR 3,000 per day
- Business -> EUR 5,000 per day

Do not omit or alter any amount, currency or package.

C. DISTINGUISH EXISTING AND NEW BEHAVIOUR

If the document describes an existing rule and then
requests a change:

- Preserve the existing rule as current-state information
  only when it is relevant to understanding the change.
- Extract the requested new rule separately.
- Do not incorrectly present an unchanged existing rule
  as a newly requested requirement.
- Do not confuse existing behaviour with proposed behaviour.

D. PRESERVE CONDITIONS

Distinguish between:

- Successful transactions
- Failed transactions
- Rejected transactions
- Pending transactions
- Reversed transactions
- Cancelled transactions

Do not assume their behaviour is identical.

E. CLASSIFICATION ACCURACY

Use NON_FUNCTIONAL only for actual quality requirements,
such as security, performance, reliability and availability.

Do not classify the following as NON_FUNCTIONAL merely
because they are not direct user-facing functions:

- Existing system capabilities
- Currency assumptions
- Account package identification assumptions
- Existing business rules
- General implementation context

Use ASSUMPTION for unconfirmed assumptions.

Use OPEN_QUESTION for unresolved decisions.

Use CONSTRAINT for explicit restrictions.

F. OPEN QUESTIONS

Extract unresolved questions separately.

Do not convert open questions into confirmed requirements.

Do not invent answers for unresolved questions.

G. SOURCE TRACEABILITY

For each requirement, include the relevant section heading
or section number.

If a requirement appears in multiple sections, include
all relevant source references in one source field.

H. AVOID INVENTION

- Do not invent business rules.
- Do not invent acceptance criteria.
- Do not assume a timezone.
- Do not assume transaction states.
- Do not assume account-level or customer-level scope
  when the document leaves it unresolved.
- Do not introduce implementation decisions absent
  from the document.

I. REQUIREMENT GRANULARITY

Each entry must express one distinct requirement or
one clearly related group of values.

Preserve mappings together when they form one business rule.

Do not create a separate requirement for every individual
package value when they belong to the same mapping.

J. IDENTIFIERS

Generate sequential IDs:

REQ-001, REQ-002, REQ-003 ...

Assign IDs only after removing duplicates.

RETURN ONLY VALID JSON:

{{
    "requirements": [
        {{
            "requirement_id": "REQ-001",
            "category": "BUSINESS_RULE",
            "description": "A complete and precise requirement.",
            "source": "Section 4"
        }}
    ]
}}

Return exactly these fields for each requirement:

- requirement_id
- category
- description
- source

Do not add explanations outside the JSON.

DOCUMENT:

{document_text}
"""

    # ---------------------------------------------------------
    # 3. Generate and validate requirements
    # ---------------------------------------------------------

    last_error = None

    for attempt in range(2):

        print(
            f"\nExtracting requirements "
            f"(attempt {attempt + 1}/2)..."
        )

        current_prompt = prompt

        # Include the validation error when retrying.
        if attempt == 1:
            current_prompt += f"""

YOUR PREVIOUS RESPONSE FAILED VALIDATION.

Validation error:
{last_error}

Please correct the response.

Remember:
- Remove semantically duplicated requirements.
- Use only the allowed categories.
- Generate sequential requirement IDs.
- Return valid JSON only.
"""

        response = generate_response(current_prompt)

        try:
            result = _parse_response(response)

            requirements = _validate_requirements(
                result["requirements"]
            )

            print(
                f"Successfully extracted "
                f"{len(requirements)} validated requirements."
            )

            # Show a compact category summary.
            category_counts = {}

            for requirement in requirements:
                category = requirement["category"]

                category_counts[category] = (
                    category_counts.get(category, 0) + 1
                )

            print("\nRequirement category summary:")

            for category, count in sorted(category_counts.items()):
                print(f"  {category}: {count}")

            return requirements

        except ValueError as error:

            last_error = str(error)

            print(
                f"Requirement extraction validation failed: "
                f"{last_error}"
            )

            if attempt == 1:
                raise ValueError(
                    f"Requirement extraction failed after retry: "
                    f"{last_error}"
                ) from error

    raise RuntimeError("Unexpected requirement extraction failure.")
