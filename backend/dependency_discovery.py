
import json
import re

from llm_service import generate_response


def discover_new_dependencies(
    requirements: list[dict],
    jira_issues: list[dict]
) -> list[dict]:

    """
    Identify potential dependencies introduced by updated requirements.

    Distinguishes existing functionality from genuinely missing
    capabilities and marks assumptions for Product Owner review.
    """

    if not requirements:
        raise ValueError("No requirements were provided.")

    if not jira_issues:
        raise ValueError("No Jira issues were provided.")

    prompt = f"""
You are an experienced software architect.

Analyse the updated requirements against the existing Jira project.

UPDATED REQUIREMENTS:
{json.dumps(requirements, indent=2)}

EXISTING JIRA ISSUES:
{json.dumps(jira_issues, indent=2)}

Identify additional capabilities or dependencies that may be
necessary to implement the updated requirements.

For every candidate:

1. Explain the capability that may be required.
2. Identify the relevant requirement IDs.
3. Check whether existing Jira issues already cover it.
4. Distinguish fully covered, partially covered and uncovered
   functionality.
5. Explain why the capability is needed.
6. State assumptions and unresolved questions.
7. Do not assume that a service or technical component exists.

Return ONLY valid JSON:

{{
    "dependencies": [
        {{
            "name": "Descriptive capability name",
            "description": "Description of the potential dependency.",
            "related_requirements": ["REQ-001"],
            "existing_coverage": "NOT_COVERED",
            "covered_by_issue_keys": [],
            "reason": "Why this capability may be required.",
            "assumptions": ["Assumption requiring verification"],
            "review_status": "REQUIRES_PRODUCT_OWNER_REVIEW"
        }}
    ]
}}

Allowed existing_coverage values:
- FULLY_COVERED
- PARTIALLY_COVERED
- NOT_COVERED
- UNCERTAIN

Rules:
- Do not use predefined dependency catalogues.
- Do not invent architecture or services.
- Do not invent Jira issue keys or requirement IDs.
- Do not propose a new dependency when existing issues
  already fully cover the capability.
- Include partially covered functionality only when a
  meaningful additional capability is required.
- Treat uncertain findings as assumptions.
- Do not create Jira stories.
- Return an empty list if no additional dependencies are justified.
- Return valid JSON only.
"""

    response_text = generate_response(prompt)

    cleaned_response = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        response_text.strip(),
        flags=re.IGNORECASE
    )

    try:
        result = json.loads(cleaned_response)

    except json.JSONDecodeError as error:
        raise ValueError(
            "AI returned invalid JSON for dependency discovery."
        ) from error

    if not isinstance(result, dict):
        raise ValueError("Unexpected AI response format.")

    dependencies = result.get("dependencies")

    if not isinstance(dependencies, list):
        raise ValueError("Dependencies must be a list.")

    valid_requirement_ids = {
        item["requirement_id"]
        for item in requirements
    }

    valid_issue_keys = {
        item["issue_key"]
        for item in jira_issues
    }

    valid_coverage_values = {
        "FULLY_COVERED",
        "PARTIALLY_COVERED",
        "NOT_COVERED",
        "UNCERTAIN"
    }

    seen_names = set()

    for dependency in dependencies:

        if not isinstance(dependency, dict):
            raise ValueError("Invalid dependency format.")

        required_fields = [
            "name",
            "description",
            "related_requirements",
            "existing_coverage",
            "covered_by_issue_keys",
            "reason",
            "assumptions",
            "review_status"
        ]

        for field in required_fields:
            if field not in dependency:
                raise ValueError(
                    f"Dependency is missing '{field}'."
                )

        name = dependency["name"]

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Dependency name cannot be empty.")

        normalized_name = name.strip().casefold()

        if normalized_name in seen_names:
            raise ValueError("Duplicate dependency names returned.")

        seen_names.add(normalized_name)

        if dependency["existing_coverage"] not in valid_coverage_values:
            raise ValueError("Invalid existing coverage value.")

        if not isinstance(dependency["related_requirements"], list):
            raise ValueError("Invalid related requirements.")

        if not set(dependency["related_requirements"]).issubset(
            valid_requirement_ids
        ):
            raise ValueError("Unknown requirement ID returned.")

        if not isinstance(dependency["covered_by_issue_keys"], list):
            raise ValueError("Invalid covered_by_issue_keys.")

        if not set(dependency["covered_by_issue_keys"]).issubset(
            valid_issue_keys
        ):
            raise ValueError("Unknown Jira issue key returned.")

        if not isinstance(dependency["assumptions"], list):
            raise ValueError("Invalid assumptions.")

        if dependency["review_status"] != "REQUIRES_PRODUCT_OWNER_REVIEW":
            raise ValueError("Invalid dependency review status.")

    return dependencies
