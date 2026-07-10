# Creative Tagger Python SDK

Python client for [Creative Tagger](https://github.com/stephenlavender/creative-tagger) — structured creative intelligence API for performance marketing.

Analyze any ad creative (video, image, carousel, landing page, email) and get back structured classification across 28 taxonomy dimensions.

## Install

```bash
pip install creative-tagger
```

## Quick Start

```python
from creative_tagger import CreativeTagger

ct = CreativeTagger(api_key="ct_...")
workspace = "Brand"

# 1. Create or update the workspace context.
ct.save_brand_context(
    workspace,
    voice="Direct, practical, proof-led",
    target_audience="Performance marketers testing paid social creative",
)

# 2. Connect Meta first so library, reports, hooks, lineage, and demographics
# can join taxonomy tags to spend and outcome data.
connect = ct.start_meta_connect(brand_name=workspace)
print(connect)  # Open the returned OAuth URL and complete Meta authorization.

# After OAuth completes, choose the ad account and sync recent performance.
ct.list_meta_adaccounts(brand_name=workspace)
ct.select_meta_adaccount("act_...", brand_name=workspace)
ct.sync_meta(brand_name=workspace, date_preset="last_30d")

# Analyze a video ad
result = ct.analyze("./ad_video.mp4", brand=workspace)
print(result.naming.standard)
# → BRAND_UGC_TalkingHead_Creator_CuriosityGap_ShopNow_9x16_V1

print(result.format)                             # → video (Media Type — auto-detected)
print(result.attributes.asset_type)              # → UGC (production class)
print(result.attributes.visual_format)           # → Talking Head (execution style)
print(result.attributes.hook_type)               # → Curiosity Gap
print(result.attributes.messaging_angle)         # → Pain Point
print(result.attributes.offer_type)              # → Percent Off

# Use workspace-scoped library, reports, hooks, lineage, and demographics.
library = ct.list_library(brand_name=workspace)
strategy = ct.creative_strategy_report(brand_name=workspace)
digest = ct.weekly_digest_report(brand_name=workspace)
taxonomy = ct.performance_by_taxonomy(brand_name=workspace)
demographics = ct.performance_demographics(brand_name=workspace)
```

## Taxonomy v2

Taxonomy v2 separates three dimensions the old model mixed together:

- **Media Type** (`result.format`) — video, image, carousel, landing_page, email,
  long_video. Auto-detected from the creative itself, never AI-classified.
- **Asset Type** (`result.attributes.asset_type`) — production class: UGC,
  Lifestyle, Studio, High Production, etc. Previously exported by this SDK as
  `production_type`.
- **Visual Format** (`result.attributes.visual_format`) — execution style:
  Talking Head, Testimonial, Demo, etc. Previously exported as `creative_type`.
  `Static Image` and `Carousel` are media types and are no longer valid Visual
  Format values.

`messaging_angle` (`result.attributes.messaging_angle`) is the canonical angle
key. `to_row()` exports one column per canonical dimension key, including
`media_type`, `asset_type`, and `visual_format`.

## Batch Analysis

```python
results = ct.analyze_batch(["ad1.mp4", "ad2.jpg", "ad3.png"], brand="Brand")

# Export to CSV-ready rows
import csv
rows = [r.to_row() for r in results]
```

## Async Support

```python
result = await ct.analyze_async("./ad.mp4", brand="Brand")
```

## Local Development

Point to a local Creative Tagger API:

```python
ct = CreativeTagger(base_url="http://localhost:8000")
```

## License

MIT
