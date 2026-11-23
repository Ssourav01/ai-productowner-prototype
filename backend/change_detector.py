
from semantic_analyzer import analyze_semantic_relevance


def detect_changes(
    requirements: list[dict],
    jira_issues: list[dict]
) -> dict:

    """
    Identify Jira issues affected by updated requirements.

    Uses semantic analysis to classify each issue and
    organises the results for further impact analysis.
    """

    analysis_results = analyze_semantic_relevance(
        requirements,
        jira_issues
    )

    direct_impacts = []
    indirect_impacts = []
    unaffected_issues = []

    for result in analysis_results:

        classification = result["classification"]

        if classification == "DIRECT":
            direct_impacts.append(result)

        elif classification == "INDIRECT":
            indirect_impacts.append(result)

        elif classification == "NOT_AFFECTED":
            unaffected_issues.append(result)

    return {
        "summary": {
            "total_issues_analyzed": len(analysis_results),
            "directly_affected": len(direct_impacts),
            "indirectly_affected": len(indirect_impacts),
            "unaffected": len(unaffected_issues)
        },
        "direct_impacts": direct_impacts,
        "indirect_impacts": indirect_impacts,
        "unaffected_issues": unaffected_issues
    }
