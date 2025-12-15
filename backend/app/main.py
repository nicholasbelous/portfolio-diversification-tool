from fastapi import FastAPI

app = FastAPI(
    title="Portfolio Diversification API",
    version="0.1.0"
)

@app.get("/")
def riit():
    return {"status": "ok"}