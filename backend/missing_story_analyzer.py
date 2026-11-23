
import json
import re

from llm_service import generate_response


def identify_missing_stories(
    requirements: list[dict],
    jira_issues: list[dict],
    dependencies: list[dict]
) -> list[dict]:

    """
    Identify genuinely missing functionality by comparing updated
    requirements against the complete set of existing Jira issues.

    These are candidate stories only. They must be reviewed and
    approved by the Product Owner before Jira creation.
    """

    # ---------------------------------------------------------
    # 1. Validate input
    # ---------------------------------------------------------

    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Requirements must be a non-empty list.")

    if not isinstance(jira_issues, list):
        raise ValueError("Jira issues must be a list.")

    if not isinstance(dependencies, list):
        raise ValueError("Dependencies must be a list.")

    # Collect valid requirement IDs, Jira keys and dependency names.

    valid_requirement_ids = {
        item.get("requirement_id")
        for item in requirements
        if item.get("requirement_id")
    }

    valid_issue_keys = {
        item.get("issue_key")
        for item in jira_issues
        if item.get("issue_key")
    }

    valid_dependency_names = {
        item.get("name")
        for item in dependencies
        if item.get("name")
    }

    # ---------------------------------------------------------
    # 2. Prepare analysis prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an experienced Product Owner and Business Analyst.

Your task is to identify genuinely missing functional capabilities
introduced or required by the updated requirements.

Analyse the COMPLETE information below.

UPDATED REQUIREMENTS:
{json.dumps(requirements, indent=2)}

ALL EXISTING JIRA ISSUES:
{json.dumps(jira_issues, indent=2)}

POTENTIAL NEW DEPENDENCIES:
{json.dumps(dependencies, indent=2)}

IMPORTANT ANALYSIS PROCESS:

Step 1:
Understand the functionality required by each updated requirement.

Step 2:
Inspect ALL existing Jira issues, including their:
- Summary
- Description
- Issue type
- Parent epic
- Linked issues

Step 3:
Determine whether existing Jira issues already implement the
required functionality.

Consider functionality covered even if the Jira issue uses
different wording from the requirement.

Step 4:
Classify the coverage of each potential capability:

- NOT_COVERED:
  No existing Jira issue adequately addresses the capability.

- PARTIALLY_COVERED:
  Existing issues address some aspects, but a distinct
  functional capability is still missing.

- FULLY_COVERED:
  Existing Jira issues already address the capability.

- UNCERTAIN:
  Available information is insufficient to determine coverage.

Step 5:
Propose candidate stories ONLY for genuinely missing
or partially covered functional capabilities.

Do not create a new story simply because an existing story
needs its description, acceptance criteria or implementation
details updated. Such changes belong in existing issue updates.

OUTPUT FORMAT:

Return ONLY valid JSON in this format:

{{
    "missing_stories": [
        {{
            "title": "Short descriptive title",
            "description": "As a [user], I want [capability], so that [benefit].",
            "reason": "Why this is genuinely missing",
            "coverage_status": "NOT_COVERED",
            "coverage_evidence": [
                {{
                    "issue_key": "SDBP-2",
                    "explanation": "What this existing issue covers and what remains missing."
                }}
            ],
            "related_requirements": ["REQ-001"],
            "related_dependencies": ["Dependency name"],
            "assumptions": [],
            "review_status": "REQUIRES_PRODUCT_OWNER_REVIEW"
        }}
    ]
}}

IMPORTANT RULES:

1. Never propose functionality already fully covered by an
   existing Jira issue.

2. Compare functionality, not just matching words or keywords.

3. Do not create duplicate stories with different titles.

4. Do not propose a new story for a capability that can be
   addressed through updating an existing Jira issue.

5. Do not invent requirement IDs, Jira issue keys or dependency names.

6. Every related requirement must come from the supplied
   updated requirements.

7. Every related dependency must come from the supplied
   potential dependencies.

8. Every issue key in coverage_evidence must exist in the
   supplied Jira issues.

9. If a capability is partially covered, clearly explain
   what is already covered and what is still missing.

10. If coverage is UNCERTAIN, do not create a story.
    Record the uncertainty as an assumption only when
    appropriate for an existing candidate.

11. Do not invent technical components, architecture,
    APIs or implementation details.

12. Do not assume that a potential dependency automatically
    requires a new user story.

13. Keep confirmed requirements separate from assumptions.

14. If no genuinely missing functionality is identified,
    return an empty missing_stories list.

15. All proposed stories must require Product Owner review.
"""

    # ---------------------------------------------------------
    # 3. Call the local AI model
    # ---------------------------------------------------------

    response_text = generate_response(prompt)

    cleaned_response = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        response_text.strip(),
        flags=re.IGNORECASE
    )

    # ---------------------------------------------------------
    # 4. Parse AI response
    # ---------------------------------------------------------

    try:
        result = json.loads(cleaned_response)

    except json.JSONDecodeError as error:
        raise ValueError(
            "The AI returned invalid JSON for missing story analysis."
        ) from error

    if not isinstance(result, dict):
        raise ValueError("Unexpected AI response format.")

    missing_stories = result.get("missing_stories")

    if not isinstance(missing_stories, list):
        raise ValueError("Missing stories must be a list.")

    # ---------------------------------------------------------
    # 5. Validate every proposed story
    # ---------------------------------------------------------

    seen_titles = set()

    allowed_coverage_statuses = {
        "NOT_COVERED",
        "PARTIALLY_COVERED"
    }

    for story in missing_stories:

        if not isinstance(story, dict):
            raise ValueError("Invalid story format.")

        required_fields = [
            "title",
            "description",
            "reason",
            "coverage_status",
            "coverage_evidence",
            "related_requirements",
            "related_dependencies",
            "assumptions",
            "review_status"
        ]

        for field in required_fields:
            if field not in story:
                raise ValueError(
                    f"Story is missing the '{field}' field."
                )

        # Validate basic text fields.

        for field in ["title", "description", "reason"]:
            if not isinstance(story[field], str) or not story[field].strip():
                raise ValueError(
                    f"Story has an invalid '{field}' field."
                )

        # Prevent duplicate titles.

        normalized_title = story["title"].strip().casefold()

        if normalized_title in seen_titles:
            raise ValueError("Duplicate candidate story detected.")

        seen_titles.add(normalized_title)

        # Validate coverage classification.

        if story["coverage_status"] not in allowed_coverage_statuses:
            raise ValueError("Invalid story coverage status.")

        # Validate related requirements.

        related_requirements = story["related_requirements"]

        if not isinstance(related_requirements, list):
            raise ValueError("Invalid related_requirements format.")

        invalid_requirement_ids = (
          set(related_requirements) - valid_requirement_ids
       )

        if invalid_requirement_ids:
           raise ValueError(
           f"Story references unknown requirement IDs: "
           f"{sorted(invalid_requirement_ids)}. "
           f"Valid IDs: {sorted(valid_requirement_ids)}"
        )

        # Validate related dependencies.

        related_dependencies = story["related_dependencies"]

        if not isinstance(related_dependencies, list):
            raise ValueError("Invalid related_dependencies format.")

        if not set(related_dependencies).issubset(valid_dependency_names):
            raise ValueError("Story references an unknown dependency.")

        # Validate evidence against real Jira issues.

        coverage_evidence = story["coverage_evidence"]

        if not isinstance(coverage_evidence, list):
            raise ValueError("Invalid coverage_evidence format.")

        for evidence in coverage_evidence:

            if not isinstance(evidence, dict):
                raise ValueError("Invalid coverage evidence entry.")

            issue_key = evidence.get("issue_key")
            explanation = evidence.get("explanation")

            if issue_key not in valid_issue_keys:
                raise ValueError(
                    "Coverage evidence references an unknown Jira issue."
                )

            if not isinstance(explanation, str) or not explanation.strip():
                raise ValueError(
                    "Coverage evidence must include an explanation."
                )

        # Validate assumptions.

        if not isinstance(story["assumptions"], list):
            raise ValueError("Invalid assumptions format.")

        # Enforce Product Owner review.

        if story["review_status"] != "REQUIRES_PRODUCT_OWNER_REVIEW":
            raise ValueError("Invalid story review status.")

    # ---------------------------------------------------------
    # 6. Return validated candidate stories
    # ---------------------------------------------------------

    return missing_stories
