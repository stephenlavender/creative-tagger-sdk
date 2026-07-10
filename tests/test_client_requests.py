import json
from urllib.parse import parse_qs

import httpx
import pytest

from creative_tagger import CreativeTagger
from creative_tagger.client import AnalyzeResult


def make_client(responses=None):
    requests = []
    queued = list(responses or [])

    def handler(request):
        request.read()
        requests.append(request)
        item = queued.pop(0) if queued else {"ok": True}
        if isinstance(item, bytes):
            return httpx.Response(200, content=item, request=request)
        if isinstance(item, str):
            return httpx.Response(200, text=item, request=request)
        if isinstance(item, tuple):
            status_code, payload = item
            return httpx.Response(status_code, json=payload, request=request)
        return httpx.Response(200, json=item, request=request)

    client = CreativeTagger(
        api_key="ct_test",
        base_url="https://api.test",
        transport=httpx.MockTransport(handler),
    )
    return client, requests


def assert_request(request, method, path):
    assert request.method == method
    assert request.url.path == path
    assert request.headers["x-api-key"] == "ct_test"


def query(request):
    return dict(request.url.params)


def json_body(request):
    return json.loads(request.content.decode())


def form_body(request):
    return parse_qs(request.content.decode(), keep_blank_values=True)


def test_workspace_and_website_requests():
    client, requests = make_client()

    client.list_brand_contexts()
    client.get_brand_context("Acme")
    client.save_brand_context(
        "Acme",
        voice="Sharp",
        target_audience="DTC buyers",
        top_performers=["creator demos"],
        anti_patterns=["generic stock"],
        assets=[{"kind": "founder", "url": "https://cdn.test/founder.png"}],
        notes="Use proof early",
    )
    client.delete_brand_context("Acme")
    client.rename_workspace("Acme", "Acme Pro")
    client.start_website_ingest("https://acme.test", brand_name="Acme Pro")
    client.get_website_ingest_status(9)

    assert_request(requests[0], "GET", "/auth/brand-contexts")
    assert_request(requests[1], "GET", "/auth/brand-context")
    assert query(requests[1]) == {"brand_name": "Acme"}
    assert_request(requests[2], "POST", "/auth/brand-context")
    assert json_body(requests[2]) == {
        "brand_name": "Acme",
        "voice": "Sharp",
        "target_audience": "DTC buyers",
        "top_performers": ["creator demos"],
        "anti_patterns": ["generic stock"],
        "assets": [{"kind": "founder", "url": "https://cdn.test/founder.png"}],
        "notes": "Use proof early",
    }
    assert_request(requests[3], "DELETE", "/auth/brand-context")
    assert query(requests[3]) == {"brand_name": "Acme"}
    assert_request(requests[4], "POST", "/auth/workspace/rename")
    assert json_body(requests[4]) == {"old_name": "Acme", "new_name": "Acme Pro"}
    assert_request(requests[5], "POST", "/auth/brand-context/ingest-website")
    assert json_body(requests[5]) == {"url": "https://acme.test", "brand_name": "Acme Pro"}
    assert_request(requests[6], "GET", "/auth/brand-context/ingest-website/9")


def test_meta_connection_and_sync_requests():
    client, requests = make_client()

    client.start_meta_connect(brand_name="Acme", scopes=["ads_read"], bind_session=True)
    client.meta_status(brand_name="Acme")
    client.list_meta_adaccounts(brand_name="Acme")
    client.select_meta_adaccount("act_123", brand_name="Acme")
    client.sync_meta(
        brand_name="Acme",
        account_id="act_123",
        date_preset="last_7d",
        attribution_windows=["7d_click", "1d_view"],
    )
    client.disconnect_meta(brand_name="Acme", purge_data=True)

    assert_request(requests[0], "POST", "/auth/meta/connect/start")
    assert json_body(requests[0]) == {
        "brand_name": "Acme",
        "bind_session": True,
        "scopes": ["ads_read"],
    }
    assert_request(requests[1], "GET", "/auth/meta/status")
    assert query(requests[1]) == {"brand_name": "Acme"}
    assert_request(requests[2], "GET", "/auth/meta/adaccounts")
    assert query(requests[2]) == {"brand_name": "Acme"}
    assert_request(requests[3], "POST", "/auth/meta/adaccount")
    assert json_body(requests[3]) == {"account_id": "act_123", "brand_name": "Acme"}
    assert_request(requests[4], "POST", "/meta/sync")
    assert json_body(requests[4]) == {
        "brand_name": "Acme",
        "account_id": "act_123",
        "date_preset": "last_7d",
        "attribution_windows": ["7d_click", "1d_view"],
    }
    assert_request(requests[5], "DELETE", "/auth/meta/connection")
    assert query(requests[5]) == {"brand_name": "Acme", "purge_data": "true"}


def test_meta_backfill_requests_and_polling():
    client, requests = make_client(
        [
            {"quote_id": 7},
            {"url": "https://checkout.test"},
            {"job_id": 42},
            {"status": "queued"},
            {"status": "running"},
            {"status": "completed"},
        ]
    )

    client.quote_meta_backfill(months=6, account_id="act_123", brand_name="Acme")
    client.checkout_meta_backfill(7)
    client.start_meta_backfill(7, brand_name="Acme")
    client.get_meta_backfill_status(42)
    result = client.wait_for_meta_backfill(42, interval_seconds=0, timeout_seconds=1)

    assert result == {"status": "completed"}
    assert_request(requests[0], "GET", "/meta/backfill/quote")
    assert query(requests[0]) == {"months": "6", "account_id": "act_123", "brand_name": "Acme"}
    assert_request(requests[1], "POST", "/billing/checkout/backfill")
    assert form_body(requests[1]) == {"quote_id": ["7"]}
    assert_request(requests[2], "POST", "/meta/backfill/start")
    assert json_body(requests[2]) == {"quote_id": 7, "brand_name": "Acme"}
    assert_request(requests[3], "GET", "/meta/backfill/jobs/42")
    assert_request(requests[4], "GET", "/meta/backfill/jobs/42")
    assert_request(requests[5], "GET", "/meta/backfill/jobs/42")


def test_library_requests():
    client, requests = make_client([{}, {}, {}, {}, {}, {}, b"media-bytes", {}])

    client.list_library(
        limit=10,
        offset=5,
        search="ugc",
        format="video",
        hook="UGC",
        angle="ProbSol",
        emotion="trust",
        cta="Shop",
        talent="creator",
        offer="PctOff",
        audio="voiceover",
        season="holiday",
        sort="spend",
        brand_name="Acme",
    )
    client.bulk_update_library([{"analysis_id": 1, "filename": "new.mp4"}])
    client.library_patterns(brand_name="Acme")
    client.get_library_item(1, brand_name="Acme")
    client.update_library_item(1, {"filename": "updated.mp4"})
    client.delete_library_item(1)
    media = client.get_library_media(1, brand_name="Acme")
    client.share_library_item(1)

    assert media == b"media-bytes"
    assert_request(requests[0], "GET", "/auth/library")
    assert query(requests[0]) == {
        "limit": "10",
        "offset": "5",
        "search": "ugc",
        "format": "video",
        "hook": "UGC",
        "angle": "ProbSol",
        "emotion": "trust",
        "cta": "Shop",
        "talent": "creator",
        "offer": "PctOff",
        "audio": "voiceover",
        "season": "holiday",
        "sort": "spend",
        "brand_name": "Acme",
    }
    assert_request(requests[1], "PATCH", "/auth/library")
    assert json_body(requests[1]) == [{"analysis_id": 1, "filename": "new.mp4"}]
    assert_request(requests[2], "GET", "/auth/library/patterns")
    assert query(requests[2]) == {"brand_name": "Acme"}
    assert_request(requests[3], "GET", "/auth/library/1")
    assert query(requests[3]) == {"brand_name": "Acme"}
    assert_request(requests[4], "PATCH", "/auth/library/1")
    assert json_body(requests[4]) == {"filename": "updated.mp4"}
    assert_request(requests[5], "DELETE", "/auth/library/1")
    assert_request(requests[6], "GET", "/auth/library/1/media")
    assert query(requests[6]) == {"brand_name": "Acme"}
    assert_request(requests[7], "POST", "/auth/library/1/share")


def test_reports_hooks_lineage_demographics_requests():
    client, requests = make_client()

    client.creative_strategy_report(
        brand_name="Acme",
        date_preset="last_30d",
        # Taxonomy v2 canonical axis keys: visual_format (execution style)
        # and media_type (auto-detected format) are separate dimensions.
        rows="visual_format",
        columns="media_type",
        metrics="spend,roas",
        metric_preset="scale",
        status_focus="winner",
        report_template="next-tests",
        start_date="2026-01-01",
        end_date="2026-01-31",
        cpa_target=25.5,
        roas_target=2.1,
        minimum_spend=1000,
        learning_spend=250,
        fatigue_minimum_calendar_days=7,
        limit=12,
        watch_group_by="ad_type",
        watch_metric="roas",
        watch_signal_focus="winner",
        watch_trajectory_focus="rising",
        watch_coverage_focus="gaps",
        watch_minimum_points=3,
        watch_minimum_calendar_days=14,
        watch_maximum_gap_days=5,
        watch_limit=6,
    )
    client.weekly_digest_report(brand_name="Acme", week_ending="2026-07-05", format="markdown")
    client.performance_by_taxonomy(
        brand_name="Acme",
        dimension="hook_type",
        spend_threshold=750,
        date_preset="last_90d",
        start_date="2026-04-01",
        end_date="2026-06-30",
    )
    client.performance_demographics(brand_name="Acme", date_preset="last_30d")
    client.get_hooks(brand_name="Acme", hook_type="UGC", sort="hook_rate", limit=25, format="csv")
    client.get_lineage(brand_name="Acme", include_suggestions=False)
    client.set_lineage_parent(analysis_id=2, parent_analysis_id=1, iteration_type="hook_swap")

    assert_request(requests[0], "GET", "/reports/creative-strategy")
    assert query(requests[0]) == {
        "brand_name": "Acme",
        "date_preset": "last_30d",
        "rows": "visual_format",
        "columns": "media_type",
        "metrics": "spend,roas",
        "metric_preset": "scale",
        "status_focus": "winner",
        "report_template": "next-tests",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "cpa_target": "25.5",
        "roas_target": "2.1",
        "minimum_spend": "1000",
        "learning_spend": "250",
        "fatigue_minimum_calendar_days": "7",
        "limit": "12",
        "watch_group_by": "ad_type",
        "watch_metric": "roas",
        "watch_signal_focus": "winner",
        "watch_trajectory_focus": "rising",
        "watch_coverage_focus": "gaps",
        "watch_minimum_points": "3",
        "watch_minimum_calendar_days": "14",
        "watch_maximum_gap_days": "5",
        "watch_limit": "6",
    }
    assert_request(requests[1], "GET", "/reports/weekly-digest")
    assert query(requests[1]) == {"brand_name": "Acme", "week_ending": "2026-07-05", "format": "markdown"}
    assert_request(requests[2], "GET", "/performance/by-taxonomy")
    assert query(requests[2]) == {
        "brand_name": "Acme",
        "dimension": "hook_type",
        "spend_threshold": "750",
        "date_preset": "last_90d",
        "start_date": "2026-04-01",
        "end_date": "2026-06-30",
    }
    assert_request(requests[3], "GET", "/performance/demographics")
    assert query(requests[3]) == {
        "brand_name": "Acme",
        "date_preset": "last_30d",
        "start_date": "",
        "end_date": "",
    }
    assert_request(requests[4], "GET", "/hooks")
    assert query(requests[4]) == {
        "brand_name": "Acme",
        "hook_type": "UGC",
        "sort": "hook_rate",
        "limit": "25",
        "format": "csv",
    }
    assert_request(requests[5], "GET", "/lineage")
    assert query(requests[5]) == {"brand_name": "Acme", "include_suggestions": "false"}
    assert_request(requests[6], "POST", "/lineage/parent")
    assert json_body(requests[6]) == {
        "analysis_id": 2,
        "parent_analysis_id": 1,
        "iteration_type": "hook_swap",
    }


def test_preflight_request_shape(tmp_path):
    draft = tmp_path / "draft.txt"
    draft.write_text("draft creative", encoding="utf-8")
    client, requests = make_client()

    client.preflight(
        "Acme",
        file_paths=[str(draft)],
        file_urls=["https://cdn.test/draft.jpg"],
        version=2,
        rows="hook_type",
        columns="format",
    )

    assert_request(requests[0], "POST", "/preflight")
    assert requests[0].headers["content-type"].startswith("multipart/form-data")
    body = requests[0].content.decode()
    assert 'name="brand_name"' in body
    assert "Acme" in body
    assert 'name="file_urls"' in body
    assert "https://cdn.test/draft.jpg" in body
    assert 'name="files"; filename="draft.txt"' in body
    assert "draft creative" in body


def test_brief_requests():
    client, requests = make_client()

    client.generate_creative_brief([{"format": "video"}], brand_name="Acme", notes="More UGC")
    client.generate_brief(
        brand_name="Acme",
        brief_type="iteration",
        objective="Scale winners",
        placement="Reels 9:16",
        parent_analysis_id=10,
        iteration_type="body_swap",
    )
    client.get_brief(3)
    client.diff_brief(3, 4)
    client.render_brief(3)

    assert_request(requests[0], "POST", "/brief/generate")
    assert form_body(requests[0]) == {
        "analyses": ['[{"format": "video"}]'],
        "brand_name": ["Acme"],
        "notes": ["More UGC"],
    }
    assert_request(requests[1], "POST", "/briefs")
    assert json_body(requests[1]) == {
        "brand_name": "Acme",
        "brief_type": "iteration",
        "objective": "Scale winners",
        "placement": "Reels 9:16",
        "iteration_type": "body_swap",
        "parent_analysis_id": 10,
    }
    assert_request(requests[2], "GET", "/briefs/3")
    assert_request(requests[3], "GET", "/briefs/3/diff/4")
    assert_request(requests[4], "GET", "/briefs/3/render")


def test_voc_requests():
    client, requests = make_client()

    client.add_voc_quotes(
        quotes=["It finally made reporting simple."],
        brand_name="Acme",
        source="support",
    )
    client.get_voc_bank(brand_name="Acme", angle_type="pain", limit=20)

    assert_request(requests[0], "POST", "/voc/quotes")
    assert json_body(requests[0]) == {
        "text": "",
        "brand_name": "Acme",
        "source": "support",
        "quotes": ["It finally made reporting simple."],
    }
    assert_request(requests[1], "GET", "/voc/bank")
    assert query(requests[1]) == {"brand_name": "Acme", "angle_type": "pain", "limit": "20"}


def test_api_errors_raise_detail_message():
    client, _ = make_client([(409, {"detail": "workspace already exists"})])

    with pytest.raises(httpx.HTTPStatusError, match="workspace already exists"):
        client.rename_workspace("Acme", "Existing")


def _taxonomy_v2_response():
    """An AnalyzeResponse shaped like the taxonomy v2 API: media type at the
    top level (`format`), asset/visual split under `attributes`, canonical
    `messaging_angle`, and standard/full/compact/reporting naming."""
    return {
        "format": "video",
        "attributes": {
            "asset_type": "UGC",
            "visual_format": "Talking Head",
            "visual_style": "Lo-Fi",
            "talent": "Creator",
            "talent_age_group": "age_25_34",
            "talent_gender": "female",
            "audience": "New Moms",
            "messaging_angle": "Pain Point",
            "seasonality": "Evergreen",
            "offer_type": "Percent Off",
            "hook_type": "Curiosity Gap",
            "hook_text": "Wait until you see this",
            "cta": "Shop Now",
            "audio_type": "Voiceover + Music",
            "voiceover_tone": "Conversational",
            "emotion": "Curiosity",
            "aspect_ratio": "9x16",
            "duration": "30s",
            "duration_seconds": 28,
        },
        "naming": {
            "standard": "BRAND_UGC_TalkingHead_Creator_CuriosityGap_ShopNow_9x16_V1",
            "compact": "BRAND_TalkingHead_Creator_ShopNow_9x16_V1",
        },
        "analysis_id": 42,
        "model_used": "gemini-2.5-flash",
        "processing_time_ms": 1234,
    }


def test_analyze_result_attribute_access_uses_v2_paths():
    result = AnalyzeResult(_taxonomy_v2_response())

    assert result.format == "video"
    assert result.attributes.asset_type == "UGC"
    assert result.attributes.visual_format == "Talking Head"
    assert result.attributes.messaging_angle == "Pain Point"
    assert result.naming.standard.startswith("BRAND_UGC_TalkingHead")
    assert "hook=Curiosity Gap" in repr(result)
    assert "format=video" in repr(result)


def test_to_row_flattens_taxonomy_v2_dimensions():
    row = AnalyzeResult(_taxonomy_v2_response()).to_row()

    # Media/asset/visual are three separate v2 dimensions.
    assert row["media_type"] == "video"
    assert row["format"] == "video"
    assert row["asset_type"] == "UGC"
    assert row["visual_format"] == "Talking Head"
    # messaging_angle is the canonical angle key, read from attributes.
    assert row["messaging_angle"] == "Pain Point"
    assert row["hook_type"] == "Curiosity Gap"
    assert row["talent"] == "Creator"
    assert row["duration_seconds"] == 28
    assert row["naming_standard"].startswith("BRAND_UGC_TalkingHead")
    assert row["naming_compact"].startswith("BRAND_TalkingHead")
    assert row["analysis_id"] == 42
    # Pre-v2 export keys are gone: creative_type/production_type were renamed
    # to visual_format/asset_type, and naming.default never exists in v2.
    assert "creative_type" not in row
    assert "production_type" not in row
    assert "naming_default" not in row


def test_to_row_is_none_safe_for_sparse_responses():
    row = AnalyzeResult({"format": "image"}).to_row()

    assert row["media_type"] == "image"
    assert row["visual_format"] is None
    assert row["asset_type"] is None
    assert row["messaging_angle"] is None
    assert row["naming_standard"] is None
