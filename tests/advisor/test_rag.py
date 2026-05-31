"""Lexical retriever determinism + relevance."""

from cfn_auditor.advisor.dto import FindingInput
from cfn_auditor.advisor.rag import load_corpus, rank_passages, retrieve
from cfn_auditor.models import Severity


def _finding(rule_id: str, resource_type: str, message: str) -> FindingInput:
    return FindingInput(
        finding_id=1,
        rule_id=rule_id,
        severity=Severity.HIGH,
        resource_logical_id="X",
        resource_type=resource_type,
        message=message,
    )


def test_load_corpus_picks_up_curated_passages() -> None:
    """Every domain in the MVP rule set is represented by at least one passage."""
    passages = {p.id for p in load_corpus()}
    assert {"s3", "sg", "iam", "rds", "ec2", "cloudtrail"} <= passages


def test_rank_prefers_passage_whose_rule_id_matches() -> None:
    """Exact rule-id match outweighs incidental keyword overlap."""
    finding = _finding(
        "CFN_S3_001",
        "AWS::S3::Bucket",
        "S3 bucket has no encryption.",
    )
    ranked = rank_passages(finding, load_corpus())
    assert ranked, "expected at least one ranked passage"
    assert ranked[0].id == "s3"


def test_rank_is_deterministic_across_invocations() -> None:
    """Same input → same ordered output."""
    finding = _finding("CFN_SG_001", "AWS::EC2::SecurityGroup", "open ingress on 22")
    first = [p.id for p in rank_passages(finding, load_corpus())]
    second = [p.id for p in rank_passages(finding, load_corpus())]
    assert first == second
    assert first[0] == "sg"


def test_retrieve_top_k_truncation() -> None:
    """``retrieve`` returns at most ``top_k`` passages."""
    finding = _finding("CFN_RDS_001", "AWS::RDS::DBInstance", "StorageEncrypted absent")
    one = retrieve(finding, top_k=1)
    two = retrieve(finding, top_k=2)
    assert len(one) <= 1
    assert len(two) <= 2
    assert one[0].id == "rds"


def test_unknown_rule_id_with_keywords_still_finds_relevant_passage() -> None:
    """Even without a rule-id match, keyword overlap surfaces a relevant passage."""
    finding = _finding(
        "CFN_TEST_NEW",
        "AWS::S3::Bucket",
        "bucket encryption missing",
    )
    ranked = rank_passages(finding, load_corpus())
    assert ranked
    assert ranked[0].id == "s3"


def test_unknown_finding_returns_empty_list_when_nothing_overlaps() -> None:
    """Findings with zero overlap (rule_id and keywords) return no passages."""
    finding = _finding("CFN_FOO_999", "AWS::Foo::Bar", "totally unrelated zzz")
    assert rank_passages(finding, load_corpus()) == []
