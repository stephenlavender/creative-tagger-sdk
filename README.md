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
print(result.naming.default)
# → BRAND_UGC_Creator_LoFi_VOMus-Pop-Conv_ShopNow_9x16_30s_V1

print(result.visual.hook_type)    # → UGC
print(result.messaging_angle)     # → ProbSol
print(result.creative_type)       # → Testimonial
print(result.production_type)     # → LoFiUGC
print(result.offer_type)          # → PctOff

# Use workspace-scoped library, reports, hooks, lineage, and demographics.
library = ct.list_library(brand_name=workspace)
strategy = ct.creative_strategy_report(brand_name=workspace)
digest = ct.weekly_digest_report(brand_name=workspace)
taxonomy = ct.performance_by_taxonomy(brand_name=workspace)
demographics = ct.performance_demographics(brand_name=workspace)
```

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
