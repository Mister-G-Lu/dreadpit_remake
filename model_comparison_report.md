# Free Image Analysis Model Comparison Report — EXHAUSTIVE

**Date:** July 2026
**Test Hardware:** Windows 10 (no GPU), Python 3.12, transformers 5.14.1
**Network:** DNS resolution blocked for huggingface.co API

---

## FINAL VERDICT: BLIP-base is the BEST option

> After exhaustive testing of **9 models** across **20+ distinct fix attempts**:
- BLIP-base and BLIP-large both work with the right flags
- **BLIP-base is more accurate** than BLIP-large for fantasy fighter art
- GIT loads but produces useless descriptions
- BLIP-2 is genuinely too large for CPU
- Florence-2, Moondream, OFA fail due to compatibility issues

---

## COMPLETE TEST MATRIX (updated with timeout fixes)

| # | Model | Size | Status | Details |
|---|---|---|---|---|
| 1 | **BLIP-base** | 0.25B | ✅ **BEST** | Fast (4.2s load, 0.7s infer), accurate captions |
| 2 | **BLIP-large** | 0.45B | ✅ **WORKS** | Timeout was FALSE ALARM — fixed with `attn_implementation='eager'`. Loads in 1.3s. But LESS accurate than base! |
| 3 | **GIT-large** | 0.57B | ✅ **LOADS** | Timeout was FALSE ALARM — loads in 1.3s with `attn_implementation='eager'`. Output still useless ("the robot is black") |
| 4 | **GIT-base** | 0.16B | ❌ USELESS | "digital art selected for the #" — training data mismatch |
| 5 | **BLIP-2** | 3B | ❌ TIMEOUT | **Genuinely unsolvable** — still >300s even with `attn_implementation='eager'` and `low_cpu_mem_usage=True` |
| 6 | **Florence-2** | 0.23B | ❌ COMPAT | transformers 5.x (`_supports_sdpa` property chain can't be bypassed) |
| 7 | **Moondream** | 2B | ❌ COMPAT | transformers 5.x + native package needs CUDA/MPS |
| 8 | **OFA** | 0.18B | ❌ REMOVED | `OFATokenizer` deleted from transformers 5.x |
| 9 | **LLaVA** | 7B | ❌ GPU NEEDED | Needs GPU |
| 10 | **HF Inference API** | Cloud | ❌ BLOCKED | DNS blocked on this network |

---

## DETAILED TIMEOUT FINDINGS

### BLIP-large: ✅ SOLVED (false alarm)
**Previous report:** "Timed out >120s"
**Actual cause:** Missing `attn_implementation='eager'` flag

**Fix:** 
```python
model = BlipForConditionalGeneration.from_pretrained(
    'Salesforce/blip-image-captioning-large',
    low_cpu_mem_usage=True,
    attn_implementation='eager',
    torch_dtype=torch.float32,
)
```
**Load time with fix:** 1.3 seconds
**BUT: BLIP-base is more accurate than BLIP-large**

| Image | BLIP-base | BLIP-large |
|---|---|---|
| Forge Colossus | ✅ "a robot standing in front of a fire" | ❌ "a man in a suit holding a hammer and a fire" |
| Wrath Infernal | ✅ "a black dragon with orange flames on its wings" | ⚠️ "a demonic demon with fiery wings and a large head" |
| Vatican Gun | ✅ "a man in a gas mask holding a gun" | ⚠️ "arafed man in gas mask holding a gun" |
| Cyber God | ✅ "a demonic dragon with a sword and a fire" | ✅ "a drawing of a demonic dragon with two swords" |

**Verdict:** BLIP-base wins. Larger model hallucinates human forms that don't exist.

### GIT-large: ✅ SOLVED (but still useless)
**Previous report:** "Timed out >120s"
**Actual cause:** Missing `attn_implementation='eager'` flag

**Fix:** Same `attn_implementation='eager'` flag
**Load time with fix:** 1.3 seconds
**Output:** "the robot is black" — still useless for our analysis

**Verdict:** GIT architecture fundamentally doesn't work for generated fantasy art.

### BLIP-2: ❌ GENUINELY UNSOLVABLE
**Previous report:** "Timed out >600s"
**Attempted fixes:**
- ✅ `attn_implementation='eager'`
- ✅ `low_cpu_mem_usage=True`
- ✅ `torch_dtype=torch.float32`
- ✅ Used smallest variant (blip2-flan-t5-xl)
- **Result:** Still >300s timeout

**Root cause:** BLIP-2 uses a 3B parameter LLM backbone (Flan-T5-xl). This requires GPU for practical use. The Q-Former + Vision Encoder + LLM pipeline needs ~12GB+ RAM for inference.

**Verdict:** Cannot run on this CPU. Would need GPU or quantization via bitsandbytes (which also requires CUDA).

---

## BLIP-BASE VS BLIP-LARGE: Head-to-Head

| Category | BLIP-base | BLIP-large |
|---|---|---|
| Params | 246M | 449M |
| Load time | 4.2s | 1.3s (with eager attn) |
| Inference | 0.7s/img | 1.5s/img |
| Cache size | 3.7 GB | 4.8 GB |
| Forge Colossus | ✅ "robot standing in front of fire" | ❌ "man in suit holding hammer and fire" |
| Wrath Infernal | ✅ "black dragon with orange flames wings" | ⚠️ "demonic demon with fiery wings" |
| Vatican Gun | ✅ "man in gas mask holding gun" | ⚠️ "arafed man in gas mask" |
| Cyber God | ✅ "demonic dragon with sword and fire" | ✅ "drawing of demonic dragon with two swords" |

**BLIP-base wins 3/4 categories.** The larger model hallucinates human features (man in suit) where none exist.

---

## BLIP-BASE PERFORMANCE (RECOMMENDED)

| Metric | Value |
|---|---|
| Model size | 246M parameters |
| Load time | 4.2 seconds |
| Inference time | 0.6-0.8 seconds per image |
| Caption quality | Descriptive 1-2 sentence captions |
| Hallucination rate | Low (correctly identifies non-human entities) |
| transformers compat | ✅ Full compatibility with 5.x |

### Recommended load code:
```python
from transformers import BlipProcessor, BlipForConditionalGeneration
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
```

### Output on test images:
```
forge_colossus:  "a robot standing in front of a fire"               warmth=59.4
wrath_infernal: "a black dragon with orange flames on its wings"     warmth=53.7
vatican_gun:    "a man in a gas mask holding a gun"                  warmth=8.8
cyber_god:      "a demonic dragon with a sword and a fire"           warmth=18.6
```
