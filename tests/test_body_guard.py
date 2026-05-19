import pytest
import gzip
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from src.api.middleware import BodyGuardMiddleware

app = FastAPI()
app.add_middleware(BodyGuardMiddleware, max_compressed_size=1000, max_uncompressed_size=5000, max_ratio=10)

@app.post("/upload")
async def upload(request: Request):
    body = await request.body()
    return {"size": len(body)}

client = TestClient(app)

def test_normal_gzip_payload():
    data = b"Hello, normal payload!"
    compressed = gzip.compress(data)
    response = client.post("/upload", content=compressed, headers={"Content-Encoding": "gzip", "Content-Length": str(len(compressed))})
    assert response.status_code == 200
    assert response.headers["X-Body-Guard"] == "ok"

def test_gzip_bomb_expansion_ratio():
    # Create a highly compressible payload (lots of zeros)
    data = b"0" * 20000
    compressed = gzip.compress(data)
    
    # Send to trigger max_ratio (ratio > 10)
    response = client.post("/upload", content=compressed, headers={"Content-Encoding": "gzip"})
    
    assert response.status_code == 413
    assert "Suspicious compression ratio" in response.json()["error"]
    assert response.headers["X-Body-Guard"] == "rejected"

def test_gzip_bomb_uncompressed_limit():
    # We'll set limits on middleware to trigger uncompressed size easily
    app2 = FastAPI()
    app2.add_middleware(BodyGuardMiddleware, max_compressed_size=10000, max_uncompressed_size=500, max_ratio=50)
    
    @app2.post("/upload")
    async def upload2(request: Request):
        return {"ok": True}
        
    client2 = TestClient(app2)
    
    data = b"A" * 1000
    compressed = gzip.compress(data)
    
    response = client2.post("/upload", content=compressed, headers={"Content-Encoding": "gzip"})
    
    assert response.status_code == 413
    assert "Uncompressed limit exceeded" in response.json()["error"]
    assert response.headers["X-Body-Guard"] == "rejected"
