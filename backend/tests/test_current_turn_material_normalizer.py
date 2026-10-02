from app.agent.control.current_turn_materials import (
    CurrentMaterialSource,
    CurrentTurnMaterialNormalizer,
)
from app.schemas.unified_agent import AgentTurnMaterials


PROFILE = "https://www.xiaohongshu.com/user/profile/user-1?xsec_token=a%2Bb%3D&xsec_source=pc_user&z=last"
NOTE = "https://www.xiaohongshu.com/explore/note-1?xsec_token=n-token&xsec_source=pc_search&source=web_explore_feed"


def normalize(text, existing=None):
    return CurrentTurnMaterialNormalizer().normalize(text, existing)


def test_plain_profile_url_is_classified_and_preserved_exactly():
    result = normalize(f"研究这个账号：\n{PROFILE}")
    assert result.profile_urls == [PROFILE]
    assert result.note_urls == []


def test_plain_note_url_is_classified_and_preserved_exactly():
    result = normalize(f"分析这篇：\n{NOTE}")
    assert result.note_urls == [NOTE]
    assert result.profile_urls == []


def test_markdown_profile_extracts_only_hyperlink_target():
    result = normalize(f"研究：[账号]({PROFILE})")
    assert result.profile_urls == [PROFILE]


def test_profile_query_parameters_remain_byte_for_byte_unchanged():
    assert normalize(PROFILE).profile_urls[0] == PROFILE


def test_note_query_parameters_remain_byte_for_byte_unchanged():
    assert normalize(NOTE).note_urls[0] == NOTE


def test_multiple_urls_preserve_input_order_within_material_type():
    second = PROFILE.replace("user-1", "user-2").replace("a%2Bb%3D", "second")
    assert normalize(f"{PROFILE}\n{second}").profile_urls == [PROFILE, second]


def test_duplicate_exact_url_is_deduplicated():
    assert normalize(f"{PROFILE}\n{PROFILE}").profile_urls == [PROFILE]


def test_non_xhs_url_is_not_misclassified():
    result = normalize("https://example.com/user/profile/user-1?xsec_token=nope")
    assert result == AgentTurnMaterials()


def test_ordinary_text_has_empty_materials():
    assert normalize("帮我研究一个同行账号") == AgentTurnMaterials()


def test_existing_typed_materials_merge_before_text_materials_without_reordering_queries():
    existing_note = NOTE.replace("note-1", "note-existing")
    result = normalize(PROFILE, AgentTurnMaterials(note_urls=[existing_note]))
    assert result.note_urls == [existing_note]
    assert result.profile_urls == [PROFILE]


def test_explicit_material_provenance_is_preserved():
    result = CurrentTurnMaterialNormalizer().normalize_with_provenance(
        "比较这些账号",
        AgentTurnMaterials(profile_urls=[PROFILE]),
    )
    assert result.materials.profile_urls == [PROFILE]
    assert result.items[0].source == CurrentMaterialSource.EXPLICIT_MATERIAL


def test_same_url_from_text_and_explicit_material_is_canonicalized_as_both():
    result = CurrentTurnMaterialNormalizer().normalize_with_provenance(
        f"分析这个账号：\n{PROFILE}",
        AgentTurnMaterials(profile_urls=[PROFILE]),
    )
    assert result.materials.profile_urls == [PROFILE]
    assert len(result.items) == 1
    assert result.items[0].source == CurrentMaterialSource.BOTH
