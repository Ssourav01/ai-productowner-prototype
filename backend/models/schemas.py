
from typing import Any, Optional
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    requirement_id: str
    description: str
    source: Optional[str] = None


class JiraIssue(BaseModel):
    issue_key: str
    summary: str
    issue_type: str
    description: str = ""
    status: Optional[str] = None
    priority: Optional[str] = None
    linked_issues: list[str] = Field(default_factory=list)


class ImpactedIssue(BaseModel):
    issue_key: str
    impact_level: str
    reason: str
    confidence: float = Field(ge=0, le=1)


class ProposedStory(BaseModel):
    summary: str
    description: str
    issue_type: str
    related_issues: list[str] = Field(default_factory=list)
    is_new_issue: bool = False


class AnalysisResult(BaseModel):
    extracted_requirements: list[Requirement]
    impacted_issues: list[ImpactedIssue]
    proposed_changes: list[ProposedStory]
    new_dependencies: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approved: bool
    approved_changes: list[dict[str, Any]] = Field(default_factory=list)
