# GCA Extraction Agent

Automatically extracts structured data from French Grid Connection Agreements (CRAC / Convention de raccordement).

## Deploy in 5 minutes → share a link with your team

### 1. Put this folder on GitHub
- Go to [github.com](https://github.com) and create a free account if needed
- Create a **New repository** (name it `gca-agent`, set it to Private)
- Upload the two files: `app.py` and `requirements.txt`

### 2. Deploy on Streamlit Cloud
- Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
- Click **New app** → select your `gca-agent` repo → main file: `app.py`
- Under **Advanced settings → Secrets**, paste this (with your real key):
  ```
  ANTHROPIC_API_KEY = "sk-ant-..."
  ```
- Click **Deploy** — done in ~1 minute

### 3. Share the link
You'll get a URL like `https://yourname-gca-agent.streamlit.app`  
Send it to your colleagues — they just open it and drop a PDF. Nothing to install.

---
## How it works
1. Upload a CRAC PDF
2. Click **Extract Data** — Claude reads the document and fills all 24 fields
3. Review and edit any field if needed (fields not found are highlighted in red)
4. Download as CSV or TSV to paste into Excel
