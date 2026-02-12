from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import pandas as pd
import os

app = FastAPI(title="TB Notification Expiry System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "tb_notifications.csv")

documents = []

if not os.path.exists(csv_path):
    print(f"❌ ERROR: File not found at {csv_path}")
    df = pd.DataFrame()
else:
    try:
        df = pd.read_csv(csv_path)
        print("✅ CSV Loaded Successfully")
        print("Columns found:", df.columns)
    except Exception as e:
        print("❌ Error reading CSV:", e)
        df = pd.DataFrame()

base_date = datetime.utcnow() - timedelta(days=180)

if not df.empty:
    for index, row in df.iterrows():
        try:
            # Try to auto-detect state column
            state_column = None
            for col in df.columns:
                if "state" in col.lower():
                    state_column = col
                    break

            if not state_column:
                state_column = df.columns[0]

            state = row[state_column]

            # Try to detect numeric column automatically
            numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns

            if len(numeric_columns) > 0:
                total = row[numeric_columns[0]]
            else:
                total = 0

            # Create simulated last_verified date
            last_verified = base_date - timedelta(days=index * 7)

            documents.append({
                "id": int(index),
                "title": f"TB Notifications - {state}",
                "notifications_total": int(total) if pd.notna(total) else 0,
                "last_verified": last_verified
            })

        except Exception as e:
            print(f"⚠️ Skipping row {index}: {e}")
            continue

print(f"📊 Total Documents Loaded: {len(documents)}")


def evaluate_document(doc):
    now = datetime.utcnow()
    age_days = (now - doc["last_verified"]).days

    if age_days < 120:
        status = "SAFE"
        freshness_score = 90
        explanation = "Recently verified public health data."
    elif age_days < 240:
        status = "RISKY"
        freshness_score = 60
        explanation = "Data aging. Review recommended."
    else:
        status = "EXPIRED"
        freshness_score = 20
        explanation = "Data outdated. Re-verification required."

    return {
        "id": doc["id"],
        "title": doc["title"],
        "notifications_total": doc["notifications_total"],
        "status": status,
        "freshness_score": freshness_score,
        "explanation": explanation
    }


@app.get("/")
def root():
    return {"message": "TB Notification Expiry System Running"}

@app.get("/documents")
def list_documents():
    return [evaluate_document(doc) for doc in documents]

@app.post("/documents/{doc_id}/use")
def use_document(doc_id: int):
    doc = next((d for d in documents if d["id"] == doc_id), None)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    evaluated = evaluate_document(doc)

    if evaluated["status"] == "EXPIRED":
        raise HTTPException(
            status_code=403,
            detail="Blocked: Data expired and cannot be used."
        )

    return {
        "message": "Action allowed",
        "document_status": evaluated["status"]
    }
