"""Parser tests — YAML/JSON CFN templates → normalised Template/Resource model.

Tests are TDD-first: they specify the contract for parse_template before the
implementation lands. We verify:
  * YAML with short-form intrinsics normalises to full-form dicts.
  * The same template expressed as JSON produces an equal model.
  * Resources expose logical_id, type, and properties.
  * Malformed YAML and malformed JSON raise MalformedTemplateError.
  * Inputs over the size cap raise TemplateTooLargeError.
  * Templates without a Resources mapping raise NotACloudFormationTemplateError.
  * Empty input is rejected with a clear domain error.
"""

import json

import pytest

from cfn_auditor.parser import (
    MalformedTemplateError,
    NotACloudFormationTemplateError,
    Resource,
    Template,
    TemplateParseError,
    TemplateTooLargeError,
    parse_template,
)

YAML_TEMPLATE_SHORT_TAGS = """\
AWSTemplateFormatVersion: "2010-09-09"
Description: Bucket with short-form intrinsics.
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketNameParam
      Tags:
        - Key: Owner
          Value: !Sub "${AWS::StackName}-owner"
        - Key: Arn
          Value: !GetAtt OtherBucket.Arn
  OtherBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: other
"""

JSON_TEMPLATE_FULL_FORMS = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "Bucket with short-form intrinsics.",
    "Resources": {
        "MyBucket": {
            "Type": "AWS::S3::Bucket",
            "Properties": {
                "BucketName": {"Ref": "BucketNameParam"},
                "Tags": [
                    {"Key": "Owner", "Value": {"Fn::Sub": "${AWS::StackName}-owner"}},
                    {"Key": "Arn", "Value": {"Fn::GetAtt": ["OtherBucket", "Arn"]}},
                ],
            },
        },
        "OtherBucket": {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": "other"},
        },
    },
}


def test_parse_yaml_with_short_tags_normalises_to_full_form() -> None:
    """!Ref/!Sub/!GetAtt short-tag YAML normalises to full-form CFN intrinsics."""
    template = parse_template(YAML_TEMPLATE_SHORT_TAGS, "bucket.yaml")

    assert isinstance(template, Template)
    assert template.name == "bucket.yaml"
    assert template.description == "Bucket with short-form intrinsics."
    assert {r.logical_id for r in template.resources} == {"MyBucket", "OtherBucket"}

    my_bucket = template.resource("MyBucket")
    assert my_bucket.type == "AWS::S3::Bucket"
    assert my_bucket.properties["BucketName"] == {"Ref": "BucketNameParam"}

    tags = my_bucket.properties["Tags"]
    assert tags[0]["Value"] == {"Fn::Sub": "${AWS::StackName}-owner"}
    assert tags[1]["Value"] == {"Fn::GetAtt": ["OtherBucket", "Arn"]}


def test_parse_json_template_yields_equivalent_model() -> None:
    """An equivalent JSON template parses to a model equal to the YAML parse."""
    yaml_template = parse_template(YAML_TEMPLATE_SHORT_TAGS, "bucket.yaml")
    json_template = parse_template(json.dumps(JSON_TEMPLATE_FULL_FORMS), "bucket.json")

    assert json_template.description == yaml_template.description
    assert {r.logical_id for r in json_template.resources} == {
        r.logical_id for r in yaml_template.resources
    }

    yaml_bucket = yaml_template.resource("MyBucket").properties
    json_bucket = json_template.resource("MyBucket").properties
    assert yaml_bucket == json_bucket


def test_resource_exposes_logical_id_type_and_properties() -> None:
    """Resource DTO exposes logical_id, type, and properties dict."""
    template = parse_template(YAML_TEMPLATE_SHORT_TAGS, "bucket.yaml")
    other = template.resource("OtherBucket")
    assert isinstance(other, Resource)
    assert other.logical_id == "OtherBucket"
    assert other.type == "AWS::S3::Bucket"
    assert other.properties == {"BucketName": "other"}


def test_parse_accepts_bytes_input() -> None:
    """parse_template accepts raw bytes (UTF-8) as input."""
    template = parse_template(YAML_TEMPLATE_SHORT_TAGS.encode("utf-8"), "bucket.yaml")
    assert template.resource("MyBucket").type == "AWS::S3::Bucket"


def test_all_short_tags_normalise() -> None:
    """Every supported short tag normalises to its CFN full-form name."""
    yaml_text = """\
Resources:
  R:
    Type: AWS::Test::Thing
    Properties:
      Ref: !Ref X
      GetAtt: !GetAtt A.B
      Sub: !Sub "${X}"
      Join: !Join ["-", [a, b]]
      Select: !Select [0, [a, b]]
      Split: !Split ["-", "a-b"]
      GetAZs: !GetAZs ""
      ImportValue: !ImportValue Other
      Base64: !Base64 "x"
      Cidr: !Cidr [10.0.0.0/16, 1, 8]
      FindInMap: !FindInMap [M, K, V]
      If: !If [C, a, b]
      Condition: !Condition Cond
      And: !And [{Condition: A}, {Condition: B}]
      Or: !Or [{Condition: A}, {Condition: B}]
      Not: !Not [{Condition: A}]
      Equals: !Equals [a, a]
"""
    props = parse_template(yaml_text, "tags.yaml").resource("R").properties
    assert props["Ref"] == {"Ref": "X"}
    assert props["GetAtt"] == {"Fn::GetAtt": ["A", "B"]}
    assert props["Sub"] == {"Fn::Sub": "${X}"}
    assert props["Join"] == {"Fn::Join": ["-", ["a", "b"]]}
    assert props["Select"] == {"Fn::Select": [0, ["a", "b"]]}
    assert props["Split"] == {"Fn::Split": ["-", "a-b"]}
    assert props["GetAZs"] == {"Fn::GetAZs": ""}
    assert props["ImportValue"] == {"Fn::ImportValue": "Other"}
    assert props["Base64"] == {"Fn::Base64": "x"}
    assert props["Cidr"] == {"Fn::Cidr": ["10.0.0.0/16", 1, 8]}
    assert props["FindInMap"] == {"Fn::FindInMap": ["M", "K", "V"]}
    assert props["If"] == {"Fn::If": ["C", "a", "b"]}
    assert props["Condition"] == {"Condition": "Cond"}
    assert props["And"] == {"Fn::And": [{"Condition": "A"}, {"Condition": "B"}]}
    assert props["Or"] == {"Fn::Or": [{"Condition": "A"}, {"Condition": "B"}]}
    assert props["Not"] == {"Fn::Not": [{"Condition": "A"}]}
    assert props["Equals"] == {"Fn::Equals": ["a", "a"]}


def test_getatt_string_form_normalises_to_list() -> None:
    """!GetAtt LogicalId.Attribute normalises to ['LogicalId', 'Attribute']."""
    yaml_text = """\
Resources:
  R:
    Type: AWS::Test::Thing
    Properties:
      A: !GetAtt Bucket.Arn
      B: !GetAtt Bucket.Tags.0.Value
"""
    props = parse_template(yaml_text, "getatt.yaml").resource("R").properties
    assert props["A"] == {"Fn::GetAtt": ["Bucket", "Arn"]}
    assert props["B"] == {"Fn::GetAtt": ["Bucket", "Tags.0.Value"]}


def test_malformed_yaml_raises_malformed_template_error() -> None:
    """Syntactically invalid YAML surfaces a MalformedTemplateError."""
    with pytest.raises(MalformedTemplateError) as excinfo:
        parse_template("Resources: : :\n  bad", "bad.yaml")
    assert isinstance(excinfo.value, TemplateParseError)
    assert "bad.yaml" in str(excinfo.value)


def test_malformed_json_raises_malformed_template_error() -> None:
    """Truncated JSON surfaces a MalformedTemplateError."""
    with pytest.raises(MalformedTemplateError):
        parse_template('{"Resources": {"Foo": {"Type": "AWS::S3::Bucket"', "bad.json")


def test_oversize_input_raises_template_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inputs larger than max_template_bytes raise TemplateTooLargeError."""
    monkeypatch.setenv("CFN_AUDITOR_MAX_TEMPLATE_BYTES", "64")
    from cfn_auditor.config import get_settings

    get_settings.cache_clear()
    try:
        big = "Resources:\n  R:\n    Type: AWS::S3::Bucket\n" + ("# " * 200)
        with pytest.raises(TemplateTooLargeError) as excinfo:
            parse_template(big, "big.yaml")
        assert "64" in str(excinfo.value) or "size" in str(excinfo.value).lower()
    finally:
        get_settings.cache_clear()


def test_missing_resources_raises_not_a_cfn_template() -> None:
    """A YAML mapping without a Resources key is not a CFN template."""
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template("Description: just docs\n", "no-resources.yaml")


def test_empty_resources_raises_not_a_cfn_template() -> None:
    """An empty Resources mapping is not a CFN template."""
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template("Resources: {}\n", "empty-resources.yaml")


def test_top_level_not_mapping_raises_not_a_cfn_template() -> None:
    """A top-level YAML list is not a CFN template."""
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template("- one\n- two\n", "list.yaml")


def test_empty_input_raises_not_a_cfn_template() -> None:
    """Empty input is not a CFN template."""
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template("", "empty.yaml")


def test_resource_lookup_unknown_id_raises_key_error() -> None:
    """Template.resource() raises KeyError for an unknown logical id."""
    template = parse_template(YAML_TEMPLATE_SHORT_TAGS, "bucket.yaml")
    with pytest.raises(KeyError):
        template.resource("DoesNotExist")


def test_non_string_keyed_resources_rejected() -> None:
    """Resources whose keys are not strings (e.g. integers) are rejected."""
    yaml_text = "Resources:\n  42:\n    Type: AWS::S3::Bucket\n"
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template(yaml_text, "intkey.yaml")


def test_resource_without_type_rejected() -> None:
    """A resource entry missing a Type field is malformed CFN."""
    yaml_text = "Resources:\n  R:\n    Properties: {}\n"
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template(yaml_text, "no-type.yaml")


def test_resource_value_not_mapping_rejected() -> None:
    """A resource whose value is not a mapping is rejected."""
    yaml_text = "Resources:\n  R: not-a-mapping\n"
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template(yaml_text, "scalar-resource.yaml")


def test_null_properties_treated_as_empty_dict() -> None:
    """A resource with Properties: null is treated as having no properties."""
    yaml_text = "Resources:\n  R:\n    Type: AWS::S3::Bucket\n    Properties: ~\n"
    template = parse_template(yaml_text, "null-props.yaml")
    assert template.resource("R").properties == {}


def test_non_mapping_properties_rejected() -> None:
    """A resource whose Properties is a list, not a mapping, is rejected."""
    yaml_text = "Resources:\n  R:\n    Type: AWS::S3::Bucket\n    Properties: [a, b]\n"
    with pytest.raises(NotACloudFormationTemplateError):
        parse_template(yaml_text, "list-props.yaml")


def test_non_string_description_dropped() -> None:
    """A non-string Description is silently dropped (description is optional)."""
    yaml_text = (
        "Description:\n  - a list\n  - of strings\n"
        "Resources:\n  R:\n    Type: AWS::S3::Bucket\n    Properties: {}\n"
    )
    template = parse_template(yaml_text, "weird-desc.yaml")
    assert template.description is None


def test_invalid_utf8_bytes_rejected() -> None:
    """Bytes that are not valid UTF-8 raise MalformedTemplateError."""
    with pytest.raises(MalformedTemplateError):
        parse_template(b"\xff\xfe\xfa", "binary.yaml")


def test_intrinsic_with_mapping_argument_supported() -> None:
    """An intrinsic taking a mapping (e.g. !Sub with a variable map) is supported."""
    yaml_text = """\
Resources:
  R:
    Type: AWS::Test::Thing
    Properties:
      Sub: !Sub
        - "${A}-${B}"
        - A: one
          B: two
"""
    props = parse_template(yaml_text, "submap.yaml").resource("R").properties
    assert props["Sub"] == {"Fn::Sub": ["${A}-${B}", {"A": "one", "B": "two"}]}


def test_unknown_short_tag_preserved_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown !Tag is preserved as opaque data; other resources stay intact."""
    yaml_text = """\
Resources:
  Good:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: keep-me
  Exotic:
    Type: AWS::Test::Thing
    Properties:
      Weird: !FutureFn some-value
"""
    with caplog.at_level("WARNING", logger="cfn_auditor.parser.loader"):
        template = parse_template(yaml_text, "exotic.yaml")

    assert {r.logical_id for r in template.resources} == {"Good", "Exotic"}
    assert template.resource("Good").properties == {"BucketName": "keep-me"}
    assert template.resource("Exotic").properties == {"Weird": {"!FutureFn": "some-value"}}

    assert any(
        "!FutureFn" in record.getMessage() and record.levelname == "WARNING"
        for record in caplog.records
    ), "Expected a warning naming the unknown tag."


def test_known_short_tag_takes_precedence_over_unknown_fallback() -> None:
    """Specific constructors win over the !-prefix multi-constructor fallback."""
    yaml_text = """\
Resources:
  R:
    Type: AWS::Test::Thing
    Properties:
      A: !Ref X
"""
    props = parse_template(yaml_text, "precedence.yaml").resource("R").properties
    assert props["A"] == {"Ref": "X"}


def test_intrinsic_with_inline_mapping_argument() -> None:
    """An intrinsic whose argument is a YAML mapping node is supported."""
    yaml_text = """\
Resources:
  R:
    Type: AWS::Test::Thing
    Properties:
      Transform: !Transform
        Name: AWS::Include
        Parameters:
          Location: s3://bucket/key
"""
    props = parse_template(yaml_text, "transform.yaml").resource("R").properties
    assert props["Transform"] == {
        "Fn::Transform": {
            "Name": "AWS::Include",
            "Parameters": {"Location": "s3://bucket/key"},
        }
    }
