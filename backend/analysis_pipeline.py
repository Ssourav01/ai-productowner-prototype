
import json
from pathlib import Path

from document_processor import extract_document_text
from requirement_extractor import extract_requirements
from jira_service import get_project_issues
from change_detector import detect_changes
from dependency_analyzer import analyze_dependencies
from dependency_discovery import discover_new_dependencies
from missing_story_analyzer import identify_missing_stories
from story_generator import generate_story_proposals


# ---------------------------------------------------------
# Project directories
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "processed"


def run_analysis_pipeline(document_path: str) -> dict:

    """
    Run the complete requirements change impact analysis.

    Workflow:
    1. Extract document text.
    2. Extract updated requirements.
    3. Fetch existing Jira issues.
    4. Analyse affected issues.
    5. Analyse existing dependencies.
    6. Discover potential new dependencies.
    7. Identify missing functionality.
    8. Generate proposed Jira changes.

    This function does NOT update Jira.
    All proposals require Product Owner approval.
    """

    # -----------------------------------------------------
    # STEP 0: Validate uploaded document
    # -----------------------------------------------------

    document = Path(document_path)

    if not document.exists():
        raise FileNotFoundError(
            f"Requirements document not found: {document}"
        )

    if not document.is_file():
        raise ValueError("The supplied path is not a file.")

    print("\n" + "=" * 60)
    print("STARTING REQUIREMENTS CHANGE IMPACT ANALYSIS")
    print("=" * 60)

    # -----------------------------------------------------
    # STEP 1: Extract document text
    # -----------------------------------------------------

    print("\nSTEP 1: Extracting document text...")

    document_text = extract_document_text(str(document))

    if not isinstance(document_text, str) or not document_text.strip():
        raise ValueError(
            "No readable text was extracted from the document."
        )

    print("Document text extracted successfully.")

    # -----------------------------------------------------
    # STEP 2: Extract updated requirements
    # -----------------------------------------------------

    print("\nSTEP 2: Extracting updated requirements...")

    requirements = extract_requirements(document_text)

    if not isinstance(requirements, list) or not requirements:
        raise ValueError(
            "No valid requirements were extracted from the document."
        )

    print(f"Extracted {len(requirements)} requirements.")

    # -----------------------------------------------------
    # STEP 3: Fetch existing Jira issues
    # -----------------------------------------------------

    print("\nSTEP 3: Fetching existing Jira issues...")

    jira_issues = get_project_issues()

    if not isinstance(jira_issues, list) or not jira_issues:
        raise ValueError(
            "No Jira issues were retrieved. "
            "Check the Jira project configuration and permissions."
        )

    print(f"Retrieved {len(jira_issues)} Jira issues.")

    # -----------------------------------------------------
    # STEP 4: Analyse affected Jira issues
    # -----------------------------------------------------

    print("\nSTEP 4: Analysing affected Jira issues...")

    change_analysis = detect_changes(
        requirements,
        jira_issues
    )

    if not isinstance(change_analysis, dict):
        raise ValueError("Invalid impact analysis result.")

    print("Semantic impact analysis completed.")

    # -----------------------------------------------------
    # STEP 5: Analyse existing Jira dependencies
    # -----------------------------------------------------

    print("\nSTEP 5: Analysing existing Jira dependencies...")

    dependency_analysis = analyze_dependencies(
        change_analysis,
        jira_issues
    )

    if not isinstance(dependency_analysis, dict):
        raise ValueError("Invalid dependency analysis result.")

    print("Existing dependency analysis completed.")

    # -----------------------------------------------------
    # STEP 6: Discover potential new dependencies
    # -----------------------------------------------------

    print("\nSTEP 6: Discovering potential new dependencies...")

    new_dependencies = discover_new_dependencies(
        requirements,
        jira_issues
    )

    if not isinstance(new_dependencies, list):
        raise ValueError("Invalid new dependency analysis result.")

    print(
        f"Discovered {len(new_dependencies)} potential dependencies."
    )

    # -----------------------------------------------------
    # STEP 7: Identify missing functionality
    # -----------------------------------------------------

    print("\nSTEP 7: Identifying missing functionality...")

    missing_stories = identify_missing_stories(
        requirements,
        jira_issues,
        new_dependencies
    )

    if not isinstance(missing_stories, list):
        raise ValueError("Invalid missing story analysis result.")

    print(
        f"Identified {len(missing_stories)} candidate new stories."
    )

    # -----------------------------------------------------
    # STEP 8: Generate proposed Jira changes
    # -----------------------------------------------------

    print("\nSTEP 8: Generating proposed Jira changes...")

    story_proposals = generate_story_proposals(
        requirements,
        jira_issues,
        change_analysis,
        missing_stories
    )

    if not isinstance(story_proposals, dict):
        raise ValueError("Invalid story proposal result.")

    print("Story proposals generated.")

    # -----------------------------------------------------
    # STEP 9: Combine analysis results
    # -----------------------------------------------------

    analysis_result = {
        "status": "COMPLETED",

        "approval_status": "PENDING_PRODUCT_OWNER_REVIEW",

        "source_document": {
            "filename": document.name,
            "file_type": document.suffix.lower()
        },

        "requirements": requirements,

        "jira_issues_analyzed": len(jira_issues),

        "change_analysis": change_analysis,

        "dependency_analysis": dependency_analysis,

        "new_dependencies": new_dependencies,

        "missing_stories": missing_stories,

        "story_proposals": story_proposals
    }

    # -----------------------------------------------------
    # STEP 10: Save analysis results
    # -----------------------------------------------------

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = OUTPUT_DIRECTORY / "analysis_result.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            analysis_result,
            file,
            indent=4,
            ensure_ascii=False
        )

    # -----------------------------------------------------
    # STEP 11: Display analysis summary
    # -----------------------------------------------------

    summary = change_analysis.get("summary", {})

    print("\n" + "=" * 60)
    print("REQUIREMENTS CHANGE IMPACT ANALYSIS COMPLETED")
    print("=" * 60)

    print(f"Source document: {document.name}")
    print(f"Requirements extracted: {len(requirements)}")
    print(f"Jira issues analysed: {len(jira_issues)}")

    print(
        "Directly affected:",
        summary.get("directly_affected", "Not available")
    )

    print(
        "Indirectly affected:",
        summary.get("indirectly_affected", "Not available")
    )

    print(
        "Potential new dependencies:",
        len(new_dependencies)
    )

    print(
        "Candidate new stories:",
        len(missing_stories)
    )

    print(
        "Proposed existing story updates:",
        len(story_proposals.get("updated_stories", []))
    )

    print(
        "Proposed new stories:",
        len(story_proposals.get("new_stories", []))
    )

    print("\nApproval status: PENDING PRODUCT OWNER REVIEW")

    print(f"Results saved to: {output_file}")

    print("\nNo Jira issues were modified or created.")

    return analysis_result


# ---------------------------------------------------------
# Run pipeline from the terminal
# ---------------------------------------------------------

if __name__ == "__main__":

    uploaded_document = input(
        "\nEnter the uploaded PDF or DOCX file path: "
    ).strip().strip('"')

    try:
        run_analysis_pipeline(uploaded_document)

    except Exception as error:
        print("\nPipeline failed:")
        print(f"{type(error).__name__}: {error}")
