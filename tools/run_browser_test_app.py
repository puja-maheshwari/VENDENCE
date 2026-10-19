"""Explicit local QA launcher. Real Gemini except a labeled outage test flag."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_local_env


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8502)
    parser.add_argument("--synthetic-consistency-demo",action="store_true")
    parser.add_argument("--simulate-gemini-failure",action="store_true")
    args=parser.parse_args()
    load_local_env()
    os.environ["VENDENCE_PUBLIC"]="0"
    os.environ["VENDENCE_APPROVAL_POLICY"]="demo_consistency" if args.synthetic_consistency_demo else "strict"
    os.environ["VENDENCE_SYNTHETIC_DATA_ONLY"]="1" if args.synthetic_consistency_demo else "0"
    os.environ["VENDENCE_QA_MODE"]="CONTROLLED GEMINI FAILURE" if args.simulate_gemini_failure else "BROWSER QA — SYNTHETIC INPUTS"
    if args.simulate_gemini_failure:
        import workflow
        def unavailable(*args,**kwargs):
            return None,"Controlled browser QA: Gemini outage injected; no extraction was performed."
        workflow.extract_document=unavailable
    from streamlit.web import cli
    sys.argv=["streamlit","run",str(ROOT / "app.py"),"--server.address=127.0.0.1",f"--server.port={args.port}",
              "--server.headless=true","--browser.gatherUsageStats=false"]
    cli.main()


if __name__ == "__main__":main()
