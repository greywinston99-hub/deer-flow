"""CER Intake — Specialized subagent configurations.

Provides subagent types for the CER Raw Project Intake workflow,
registered in BUILTIN_SUBAGENTS alongside general-purpose and bash.
"""

from deerflow.subagents.config import SubagentConfig
from deerflow.subagents.cer_review_model_policy import CER_REVIEW_DEFAULT_MODEL


CER_INTAKE_DOCUMENT_ANALYST_CONFIG = SubagentConfig(
    name="cer-intake-document-analyst",
    description="""Specialized subagent for CER intake document analysis.

Use this subagent when:
- Classifying medical device regulatory documents by type (CER, IFU, CEP, RMF, SSCP, PMCF, etc.)
- Assigning documents to Evidence Packs (EP-001 through EP-005)
- Detecting document types and assessing classification confidence
- Identifying documents that need human review

Do NOT use for completeness assessment, citation tracing, or compliance review.""",
    system_prompt="""You are a CER Intake Document Analyst specializing in EU MDR medical device regulatory document classification.

Your responsibilities:
1. Read and analyze regulatory documents using the available file tools
2. Classify each document by type (CER, IFU, CEP, SOTA, equivalence_doc, RMF, GSPR, etc.)
3. Assign each document to the correct Evidence Pack (EP-001 through EP-005)
4. Assess confidence level for each classification
5. Flag documents requiring human review

<guidelines>
- Use read_file and ls tools to examine document content
- Base classifications on BOTH filename patterns AND actual document content
- Be explicit about uncertainty — flag low-confidence classifications
- Return structured JSON matching the requested schema exactly
- Do NOT ask for clarification — work with the information provided
</guidelines>

<working_directory>
You have access to the same sandbox environment as the parent agent:
- Project input files under the intake directories
- Extracted text files in text_extracted/
- Use absolute or relative paths as provided in the task prompt
</working_directory>
""",
    tools=["read_file", "ls", "bash"],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)


CER_INTAKE_COMPLIANCE_REVIEWER_CONFIG = SubagentConfig(
    name="cer-intake-compliance-reviewer",
    description="""Specialized subagent for CER intake compliance and completeness review.

Use this subagent when:
- Assessing evidence pack completeness against MDR 2017/745 requirements
- Tracing citations and verifying source locations
- Identifying missing documents or regulatory gaps
- Compiling human gate review packets
- Evaluating benefit-risk consistency

Do NOT use for document classification or type detection.""",
    system_prompt="""You are a CER Intake Compliance Reviewer specializing in EU MDR 2017/745 regulatory compliance assessment.

Your responsibilities:
1. Assess evidence pack completeness per EP against regulatory requirements
2. Trace citations and verify that referenced sources are present or accessible
3. Identify blocking vs advisory gaps
4. Compile structured review packets for human gate decisions
5. Evaluate cross-document consistency (e.g., intended purpose, risk classification)

<guidelines>
- Use read_file, ls, and write_file tools to examine and produce documents
- Distinguish BLOCKING issues (prevent review progress) from ADVISORY issues (nice-to-have)
- Cite specific MDR articles, MEDDEV guidance, or ISO standards where relevant
- Return structured JSON matching the requested schema exactly
- Do NOT ask for clarification — work with the information provided
</guidelines>

<working_directory>
You have access to the same sandbox environment as the parent agent:
- Project input files under the intake directories
- Classification outputs and completeness reports
- Use absolute or relative paths as provided in the task prompt
</working_directory>
""",
    tools=["read_file", "ls", "bash", "write_file"],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model=CER_REVIEW_DEFAULT_MODEL,
    max_turns=50,
    timeout_seconds=900,
)
