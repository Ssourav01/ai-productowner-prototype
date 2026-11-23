
import json
import re

from llm_service import generate_response


# Number of Jira issues analysed in each Ollama request.
BATCH_SIZE = 2


def _parse_json_response(response_text: str) -> dict:
    """Parse and validate the basic JSON response structure."""

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
        raise ValueError("The AI returned invalid JSON.") from error

    if not isinstance(result, dict):
        raise ValueError("AI response must be a JSON object.")

    if not isinstance(result.get("results"), list):
        raise ValueError("AI response does not contain a results list.")

    return result


def _analyse_batch(
    requirements: list[dict],
    jira_issues: list[dict],
    all_jira_issues: list[dict],
    batch_number: int
) -> list[dict]:
    """Analyse one batch of Jira issues."""

    target_issue_keys = {
        issue["issue_key"] for issue in jira_issues
    }

    valid_requirement_ids = {
        requirement["requirement_id"]
        for requirement in requirements
    }

    prompt = f"""
You are an expert software requirements change impact analyst.

Your task is to determine whether each TARGET JIRA ISSUE actually
requires modification because of the CONFIRMED REQUIREMENTS.

CONFIRMED REQUIREMENTS:
{json.dumps(requirements, indent=2)}

ALL JIRA ISSUES (context only):
{json.dumps(all_jira_issues, indent=2)}

TARGET JIRA ISSUES:
{json.dumps(jira_issues, indent=2)}

IMPORTANT:
Analyse only the target issues.
Return exactly one result for each target issue.

CLASSIFICATION RULES:

1. DIRECT:
Classify an issue as DIRECT only when its own existing functionality,
business rules, scope or acceptance criteria must change.

2. INDIRECT:
Classify an issue as INDIRECT only when a specific dependency or
interaction means that it may need modification because another
affected component changes.

3. NOT_AFFECTED:
Use NOT_AFFECTED when no concrete modification is justified.

REQUIRED ANALYSIS:

For every target issue:

A. Examine its actual summary, description and acceptance criteria.

B. Identify what the issue currently implements.

C. Compare its existing behaviour with the confirmed requirements.

D. Identify the exact behaviour or acceptance criterion that must
   change, if any.

E. Explain why the change is necessary.

STRICT RULES:

- Do not classify an issue as affected merely because it uses
  similar keywords.
- Do not classify an issue as affected merely because it belongs
  to an affected Epic.
- Do not classify an issue as affected merely because it is linked
  to another affected issue.
- Do not invent missing acceptance criteria.
- Do not assume existing functionality needs modification when
  the new requirement is already satisfied.
- Do not treat assumptions or open questions as confirmed
  implementation requirements.
- Do not invent new business rules.
- Do not assume a particular timezone, banking-day definition,
  transaction state or account-level scope.
- Do not assume customer-facing messages need changes unless
  confirmed requirements explicitly change their behaviour.
- A testing issue may be DIRECT when specific new test scenarios
  are required by confirmed requirements.
- An Epic may be DIRECT only when its own scope or description
  needs modification.
- Do not use a generic explanation as evidence.

REQUIREMENT REFERENCES:

- Use only the supplied confirmed requirement IDs.
- DIRECT and INDIRECT issues must reference at least one
  relevant requirement ID.
- NOT_AFFECTED issues must have an empty related_requirements list.
- Never return an empty requirement list for an affected issue.

EVIDENCE:

The evidence must identify:
1. Existing functionality from the Jira issue.
2. The relevant new confirmed requirement.
3. The exact difference between them.

If no concrete difference exists, classify the issue as NOT_AFFECTED.

OUTPUT FORMAT:

Return valid JSON only:

{{
    "results": [
        {{
            "issue_key": "Existing Jira issue key",
            "classification": "DIRECT",
            "related_requirements": ["REQ-001"],
            "confidence": 0.90,
            "evidence": "Specific existing behaviour and the exact difference introduced by the confirmed requirement.",
            "reason": "The precise modification required and why it is necessary."
        }}
    ]
}}

Expected target issue keys:
{json.dumps(sorted(target_issue_keys))}

Available confirmed requirement IDs:
{json.dumps(sorted(valid_requirement_ids))}

Return exactly one result for every expected target issue.
Do not omit or duplicate issue keys.
Do not include Markdown or explanations outside the JSON.
"""

    # Allow one retry if the AI returns an invalid response.
    last_error = None

    for attempt in range(2):

        print(
            f"\nAnalysing batch {batch_number} "
            f"(attempt {attempt + 1}/2)..."
        )

        prompt_for_attempt = prompt

        # Include the previous validation error in the retry prompt.
        if attempt == 1:
            prompt_for_attempt += f"""

YOUR PREVIOUS RESPONSE FAILED VALIDATION.

The exact validation error was:
{last_error}

Correct this error in your new response.

IMPORTANT:
- DIRECT and INDIRECT issues must reference at least one valid
  requirement ID.
- Available requirement IDs are:
  {json.dumps(sorted(valid_requirement_ids))}
- If an issue has no justified impact, classify it as NOT_AFFECTED
  and return an empty related_requirements list.
- Do not invent requirement IDs.
- Return exactly one result for each target issue.
- Return valid JSON only.
"""

        response_text = generate_response(prompt_for_attempt)

        try:
            result = _parse_json_response(response_text)
            results = result["results"]

            returned_keys = [
                item.get("issue_key")
                for item in results
                if isinstance(item, dict)
            ]

            # Check for missing, unexpected or duplicate issues.
            if (
                len(returned_keys) != len(target_issue_keys)
                or set(returned_keys) != target_issue_keys
                or len(returned_keys) != len(set(returned_keys))
            ):
                raise ValueError(
                    f"Incomplete batch response. "
                    f"Expected: {sorted(target_issue_keys)}, "
                    f"Received: {sorted(str(key) for key in returned_keys)}"
                )

            # Validate each result.
            for item in results:

                if not isinstance(item, dict):
                    raise ValueError("Invalid issue result.")

                issue_key = item.get("issue_key")

                if item.get("classification") not in {
                    "DIRECT",
                    "INDIRECT",
                    "NOT_AFFECTED"
                }:
                    raise ValueError(
                        f"Invalid classification for {issue_key}."
                    )

                related_requirements = item.get("related_requirements")

                if not isinstance(related_requirements, list):
                    raise ValueError(
                        f"Invalid requirement references for {issue_key}."
                    )

                if len(related_requirements) != len(set(related_requirements)):
                    raise ValueError(
                        f"Duplicate requirement references for {issue_key}."
                    )

                if not set(related_requirements).issubset(
                    valid_requirement_ids
                ):
                    raise ValueError(
                        f"Unknown or unconfirmed requirement ID for {issue_key}."
                    )

                if (
                    item["classification"] in {"DIRECT", "INDIRECT"}
                    and not related_requirements
                ):
                    raise ValueError(
                        f"Affected issue {issue_key} "
                        "has no related requirement IDs."
                    )

                if (
                    item["classification"] == "NOT_AFFECTED"
                    and related_requirements
                ):
                    raise ValueError(
                        f"Unaffected issue {issue_key} "
                        "must have an empty requirement list."
                    )

                confidence = item.get("confidence")

                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not 0 <= confidence <= 1
                ):
                    raise ValueError(
                        f"Invalid confidence score for {issue_key}."
                    )

                for field in ["evidence", "reason"]:

                    if (
                        not isinstance(item.get(field), str)
                        or not item[field].strip()
                    ):
                        raise ValueError(
                            f"Missing {field} for {issue_key}."
                        )

            return results

        except ValueError as error:

            last_error = str(error)

            print(f"Batch validation failed: {last_error}")

            if attempt == 1:
                raise ValueError(
                    f"Semantic analysis failed for batch {batch_number}: "
                    f"{last_error}"
                ) from error

    raise RuntimeError("Unexpected batch analysis failure.")


def analyze_semantic_relevance(
    requirements: list[dict],
    jira_issues: list[dict],
    batch_size: int = BATCH_SIZE
) -> list[dict]:
    """
    Analyse the impact of updated requirements on existing Jira issues.

    Jira issues are processed in smaller batches to reduce omissions
    from local language models.

    Returns exactly one validated result per Jira issue.
    """

    # ---------------------------------------------------------
    # 1. Validate inputs
    # ---------------------------------------------------------

    if not requirements:
        raise ValueError("No requirements were provided.")

    if not jira_issues:
        raise ValueError("No Jira issues were provided.")

    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError("Batch size must be a positive integer.")

    issue_keys = [
        issue.get("issue_key")
        for issue in jira_issues
    ]

    if any(not key for key in issue_keys):
        raise ValueError("A Jira issue is missing its issue key.")

    if len(issue_keys) != len(set(issue_keys)):
        raise ValueError("Duplicate Jira issue keys were provided.")

    requirement_ids = [
        requirement.get("requirement_id")
        for requirement in requirements
    ]

    if any(not req_id for req_id in requirement_ids):
        raise ValueError("A requirement is missing its ID.")

    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Duplicate requirement IDs were provided.")

    # ---------------------------------------------------------
    # 2. Separate confirmed requirements
    # ---------------------------------------------------------

    confirmed_requirements = [
        requirement
        for requirement in requirements
        if requirement.get("category") not in {
            "ASSUMPTION",
            "OPEN_QUESTION"
        }
    ]

    if not confirmed_requirements:
        raise ValueError(
            "No confirmed requirements are available for impact analysis."
        )

    # ---------------------------------------------------------
    # 3. Divide Jira issues into batches
    # ---------------------------------------------------------

    batches = [
        jira_issues[index:index + batch_size]
        for index in range(0, len(jira_issues), batch_size)
    ]

    print(
        f"\nStarting semantic analysis: "
        f"{len(jira_issues)} Jira issues in {len(batches)} batches."
    )

    # ---------------------------------------------------------
    # 4. Analyse each batch
    # ---------------------------------------------------------

    all_results = []

    for batch_number, batch in enumerate(batches, start=1):

        batch_results = _analyse_batch(
            confirmed_requirements,
            batch,
            jira_issues,
            batch_number
        )

        all_results.extend(batch_results)

        print(
            f"Batch {batch_number} completed: "
            f"{len(batch_results)} issues analysed."
        )

    # ---------------------------------------------------------
    # 5. Validate combined results
    # ---------------------------------------------------------

    returned_keys = [
        item["issue_key"]
        for item in all_results
    ]

    if len(returned_keys) != len(set(returned_keys)):
        raise ValueError(
            "Combined analysis contains duplicate Jira issues."
        )

    missing_keys = set(issue_keys) - set(returned_keys)
    unexpected_keys = set(returned_keys) - set(issue_keys)

    if missing_keys:
        raise ValueError(
            f"Jira issues missing from analysis: {sorted(missing_keys)}"
        )

    if unexpected_keys:
        raise ValueError(
            f"Unexpected Jira issues in analysis: {sorted(unexpected_keys)}"
        )

    print(
        f"\nSemantic analysis completed successfully: "
        f"{len(all_results)} Jira issues analysed."
    )

    return all_results
