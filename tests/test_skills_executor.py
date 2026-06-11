import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from skills.community import (
    SkillLoaderFactory,
    SkillFormat,
    CommunitySkillExecutor,
    CommunitySkill,
    Extractor,
    CrawlAction
)
from skills.executor import generate_skill_from_execution
from skills.models import TargetConfig, Parameter, ExecutionConfig, OutputConfig


@pytest.fixture
def mock_skill() -> CommunitySkill:
    return CommunitySkill(
        id="test-skill",
        name="Test Skill",
        version="1.0.0",
        author="test-author",
        description="test-description",
        tags=["test"],
        target=TargetConfig(domain="example.com", url_patterns=["example.com/*"]),
        parameters=[
            Parameter(name="page_limit", type="int", description="page limit", default=10, required=False),
            Parameter(name="search_query", type="str", description="query", required=True)
        ],
        execution=ExecutionConfig(wait_time=1, scroll=False, headless=True),
        extractors=[
            Extractor(name="title", selector="h1", type="text", required=True),
            Extractor(name="link", selector="a", type="attribute", attribute="href", required=False)
        ],
        output=OutputConfig(format="json"),
        prompt="test-prompt"
    )


def test_executor_init_and_helper_loading(mock_skill):
    # Case 1: script_path is None or does not exist
    mock_skill.script_path = None
    executor = CommunitySkillExecutor(mock_skill)
    assert executor.helper_module is None

    mock_skill.script_path = "non_existent_file.py"
    executor = CommunitySkillExecutor(mock_skill)
    assert executor.helper_module is None

    # Case 2: script_path exists, load helper successfully
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write("""
async def execute(url, params, skill):
    return {"status": "success", "data": [{"source": "helper"}]}
""")
        temp_path = f.name

    try:
        mock_skill.script_path = temp_path
        executor = CommunitySkillExecutor(mock_skill)
        assert executor.helper_module is not None
        assert hasattr(executor.helper_module, "execute")
    finally:
        os.remove(temp_path)

    # Case 3: script_path exists but dynamic loading fails
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write("invalid python syntax code here ::::")
        temp_path_invalid = f.name
    try:
        mock_skill.script_path = temp_path_invalid
        # Should not raise exception, just print error and set helper_module to None
        executor = CommunitySkillExecutor(mock_skill)
        assert executor.helper_module is None
    finally:
        os.remove(temp_path_invalid)


@pytest.mark.asyncio
async def test_executor_execute_logic(mock_skill):
    # Case 1: No helper -> default execute
    mock_skill.script_path = None
    executor = CommunitySkillExecutor(mock_skill)
    res = await executor.execute("http://example.com", {"search_query": "test"})
    assert res["status"] == "success"
    assert res["skill_id"] == "test-skill"

    # Case 2: Helper execute succeeds
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write("""
async def execute(url, params, skill):
    return {"status": "success", "data": [{"title": params.get("search_query")}]}
""")
        temp_path = f.name
    try:
        mock_skill.script_path = temp_path
        executor = CommunitySkillExecutor(mock_skill)
        res = await executor.execute("http://example.com", {"search_query": "my_query"})
        assert res["status"] == "success"
        assert res["data"] == [{"title": "my_query"}]
    finally:
        os.remove(temp_path)

    # Case 3: Helper execute raises exception
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write("""
async def execute(url, params, skill):
    raise Exception("execute error")
""")
        temp_path_err = f.name
    try:
        mock_skill.script_path = temp_path_err
        executor = CommunitySkillExecutor(mock_skill)
        res = await executor.execute("http://example.com", {"search_query": "my_query"})
        assert res["status"] == "error"
        assert "execute error" in res["message"]
    finally:
        os.remove(temp_path_err)


def test_merge_params(mock_skill):
    executor = CommunitySkillExecutor(mock_skill)

    # Required param missing
    with pytest.raises(ValueError, match="缺少必要參數: search_query"):
        executor._merge_params({})

    # Custom override and default parameter
    params = executor._merge_params({"search_query": "google"})
    assert params["search_query"] == "google"
    assert params["page_limit"] == 10  # default value

    # Explicit override of default
    params2 = executor._merge_params({"search_query": "google", "page_limit": 5})
    assert params2["page_limit"] == 5


def test_extract_data_single_vs_list(mock_skill):
    # Single mode (no extractor has multiple=True)
    executor = CommunitySkillExecutor(mock_skill)
    html_content = "<div><h1>My Title</h1><a href='/link1'>Link</a></div>"
    res = executor.extract_data(html_content)
    assert len(res) == 1
    assert res[0] == {"title": "My Title", "link": "/link1"}

    # Single mode: required field missing (h1 is not there)
    html_content_missing = "<div><a href='/link1'>Link</a></div>"
    res_missing = executor.extract_data(html_content_missing)
    assert res_missing == []

    # List mode (one extractor has multiple=True)
    list_skill = CommunitySkill(
        id="list-skill",
        name="List Skill",
        version="1.0.0",
        author="test",
        description="test",
        tags=[],
        target=TargetConfig(domain="example.com", url_patterns=[]),
        parameters=[],
        execution=ExecutionConfig(wait_time=1),
        extractors=[
            Extractor(name="item", selector=".item", type="text", multiple=True),
            Extractor(name="price", selector=".price", type="text", required=False),
            # non-multiple in list context: searches in element.parent
            Extractor(name="section", selector="h2", type="text", multiple=False)
        ],
        output=OutputConfig(format="json"),
        prompt="prompt"
    )
    executor_list = CommunitySkillExecutor(list_skill)

    # HTML structure: section has h2, followed by multiple items
    html_content_list = """
    <div>
      <h2>Category A</h2>
      <div class="item">Item 1 <span class="price">10</span></div>
      <div class="item">Item 2 <span class="price">20</span></div>
    </div>
    """
    res_list = executor_list.extract_data(html_content_list)
    assert len(res_list) == 2
    # Item 1 should have section Category A (from parent of .item)
    assert res_list[0]["item"].strip().startswith("Item 1")
    assert res_list[0]["price"] == "10"
    assert res_list[0]["section"] == "Category A"

    # Edge cases: elements matching main_extractor but not found
    html_no_items = "<div><h2>Category A</h2></div>"
    assert executor_list.extract_data(html_no_items) == []


def test_extract_element_value_types(mock_skill):
    # Setup skill with different extractor types
    types_skill = CommunitySkill(
        id="types-skill",
        name="Types Skill",
        version="1.0.0",
        author="test",
        description="test",
        tags=[],
        target=TargetConfig(domain="example.com", url_patterns=[]),
        parameters=[],
        execution=ExecutionConfig(wait_time=1),
        extractors=[
            Extractor(name="text_field", selector=".txt", type="text"),
            Extractor(name="attr_field", selector=".link", type="attribute", attribute="href"),
            Extractor(name="attr_missing_field", selector=".link", type="attribute", attribute=None),
            Extractor(name="html_field", selector=".box", type="html"),
            Extractor(name="val_field", selector="input", type="value"),
            Extractor(name="other_field", selector=".oth", type="unknown_type")
        ],
        output=OutputConfig(format="json"),
        prompt="prompt"
    )
    executor = CommunitySkillExecutor(types_skill)
    html = """
    <div>
      <div class="txt"> Hello World </div>
      <a class="link" href="https://example.com">Link</a>
      <div class="box"><span>inside</span></div>
      <input value="some_input_value"/>
      <div class="oth">Fallback Text</div>
    </div>
    """
    res = executor.extract_data(html)[0]
    assert res["text_field"] == "Hello World"
    assert res["attr_field"] == "https://example.com"
    assert res["attr_missing_field"] == "Link"
    assert "<span>inside</span>" in res["html_field"]
    assert res["val_field"] == "some_input_value"
    assert res["other_field"] == "Fallback Text"


def test_extract_regex_and_transforms():
    skill = CommunitySkill(
        id="regex-skill",
        name="Regex Skill",
        version="1.0.0",
        author="test",
        description="test",
        tags=[],
        target=TargetConfig(domain="example.com", url_patterns=[]),
        parameters=[],
        execution=ExecutionConfig(wait_time=1),
        extractors=[
            # Regex with group 1
            Extractor(name="num_grp1", selector=".price", type="text", regex=r"USD (\d+)"),
            # Regex with no groups (match group 0)
            Extractor(name="num_grp0", selector=".price", type="text", regex=r"\d+"),
            # Regex no match
            Extractor(name="num_nomatch", selector=".price", type="text", regex=r"EUR \d+"),
            # Transform replace
            Extractor(name="replaced", selector=".text", type="text", transform="replace(/hello/, 'hi')"),
            # Transform int
            Extractor(name="integer", selector=".int", type="text", transform="to_int"),
            # Transform float
            Extractor(name="floating", selector=".float", type="text", transform="to_float"),
            # Nested extractor children
            Extractor(
                name="nested",
                selector=".parent",
                type="text",
                children=[
                    Extractor(name="child1", selector=".c1", type="text"),
                    Extractor(name="child2", selector=".c2", type="text")
                ]
            )
        ],
        output=OutputConfig(format="json"),
        prompt="prompt"
    )
    executor = CommunitySkillExecutor(skill)
    html = """
    <div>
      <div class="price">USD 99</div>
      <div class="text">hello world hello</div>
      <div class="int">123</div>
      <div class="float">123.45</div>
      <div class="parent">
         <span class="c1">First</span>
         <span class="c2">Second</span>
      </div>
    </div>
    """
    res = executor.extract_data(html)[0]
    assert res["num_grp1"] == "99"
    assert res["num_grp0"] == "99"
    assert "num_nomatch" not in res
    assert res["replaced"] == "hi world hi"
    assert res["integer"] == 123
    assert res["floating"] == 123.45
    assert res["nested"] == ["First", "Second"]


def test_executor_coverage_edge_cases(mock_skill):
    from bs4 import BeautifulSoup

    # 1. Cover line 180: _extract_list when no multiple extractor exists
    executor = CommunitySkillExecutor(mock_skill)  # mock_skill has no multiple extractor
    soup = BeautifulSoup("<div></div>", "html.parser")
    res_list = executor._extract_list(soup)
    assert res_list == []

    # 2. Cover line 200: parent is None
    # Let's create a skill with a multiple extractor and a non-multiple extractor
    parent_none_skill = CommunitySkill(
        id="parent-none-skill",
        name="Parent None Skill",
        version="1.0.0",
        author="test",
        description="test",
        tags=[],
        target=TargetConfig(domain="example.com", url_patterns=[]),
        parameters=[],
        execution=ExecutionConfig(wait_time=1),
        extractors=[
            Extractor(name="item", selector="div", type="text", multiple=True),
            Extractor(name="title", selector="span", type="text", multiple=False)
        ],
        output=OutputConfig(format="json"),
        prompt="prompt"
    )
    executor_parent = CommunitySkillExecutor(parent_none_skill)
    # Mocking element with no parent
    mock_el = MagicMock()
    mock_el.parent = None
    mock_soup = MagicMock()
    mock_soup.select.return_value = [mock_el]
    res = executor_parent._extract_list(mock_soup)
    assert res == [{"item": mock_el.get_text()}]  # item is present, title is None because parent is None

    # 3. Cover line 248: attribute is missing, returns None
    attr_missing_skill = CommunitySkill(
        id="attr-missing-skill",
        name="Attr Missing Skill",
        version="1.0.0",
        author="test",
        description="test",
        tags=[],
        target=TargetConfig(domain="example.com", url_patterns=[]),
        parameters=[],
        execution=ExecutionConfig(wait_time=1),
        extractors=[
            Extractor(name="missing_attr", selector="a", type="attribute", attribute="nonexistent")
        ],
        output=OutputConfig(format="json"),
        prompt="prompt"
    )
    executor_attr = CommunitySkillExecutor(attr_missing_skill)
    html_attr = "<div><a>link without attr</a></div>"
    res_attr = executor_attr.extract_data(html_attr)
    assert res_attr == []  # no data extracted because it is None


def test_apply_transform_exceptions():
    executor = CommunitySkillExecutor(MagicMock())
    # Exception inside regex parsing or replacement should return original value
    assert executor._apply_transform("hello", "replace(/invalid[/, 'hi')") == "hello"

    # Non-numeric string with to_int / float should just return the string back
    assert executor._apply_transform("not a number", "") == "not a number"


def test_generate_skill_from_execution_func():
    skill = generate_skill_from_execution(
        skill_id="skill-123",
        skill_name="Auto Skill",
        url="https://tw.yahoo.com/news/sports",
        instruction="get sports news headings",
        extractors=[
            {"name": "heading", "selector": "h2", "type": "text", "required": True}
        ],
        execution_config={"wait_time": 5, "scroll": True},
        code="some JS code",
        prompt=None
    )

    assert skill.id == "skill-123"
    assert skill.name == "Auto Skill"
    assert skill.target.domain == "tw.yahoo.com"
    assert skill.target.url_patterns == ["tw.yahoo.com/*"]
    assert len(skill.extractors) == 1
    assert skill.extractors[0].name == "heading"
    assert skill.extractors[0].selector == "h2"
    assert skill.extractors[0].required is True
    assert skill.execution.wait_time == 5
    assert skill.execution.scroll is True
    assert "get sports news headings" in skill.prompt
    assert skill.is_auto_generated is True
