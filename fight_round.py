import json, os, sys, time, urllib.parse, statistics, requests
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

OUT = os.path.join(os.path.dirname(__file__), "fight_images")
os.makedirs(OUT, exist_ok=True)

def gen(prompt, name, seed):
    fp = os.path.join(OUT, name)
    if os.path.exists(fp) and os.path.getsize(fp) > 1000: return fp
    safe = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?model=flux&width=1024&height=1024&seed={seed}"
    for _ in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(fp, "wb") as f: f.write(r.content)
                return fp
        except: pass
        time.sleep(3)
    return None

def analyze(fp):
    img = Image.open(fp).convert("RGB")
    proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    inputs = proc(img, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(**inputs, max_length=50)
    desc = proc.decode(out[0], skip_special_tokens=True)
    px = list(img.getdata())
    r = statistics.mean([p[0] for p in px])
    g = statistics.mean([p[1] for p in px])
    b = statistics.mean([p[2] for p in px])
    return {
        "blip": desc,
        "warmth": round(r - b, 1),
        "brightness": round((r+g+b)/3, 1),
        "red_ratio": round(r / max(r+g+b, 1), 3),
        "avg_r": round(r,1), "avg_g": round(g,1), "avg_b": round(b,1),
    }

if __name__ == "__main__" and len(sys.argv) >= 3:
    fname = sys.argv[1]
    prompt = sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    fp = gen(prompt, fname, seed)
    if fp:
        result = analyze(fp)
        print(json.dumps(result))
    else:
        print("ERROR: Failed to generate")
